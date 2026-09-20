/**
 * Wi-Fi Presence Estimation — Network Operations Center Dashboard Application
 * Handles WebSocket event streams, Chart.js timeline, animated gauges, and demo controls.
 */

// State
let occupancyChart = null;
const MAX_CHART_POINTS = 25;
const MAX_FEED_ITEMS = 150;
let isFeedHovered = false;

const roomState = {
  "Room 101": { occupancyPct: 0, estimated: 0, capacity: 40, confidenceAvg: 0.0, activeSeen: 0 },
  "Room 102": { occupancyPct: 0, estimated: 0, capacity: 35, confidenceAvg: 0.0, activeSeen: 0 },
  "Lab 1":    { occupancyPct: 0, estimated: 0, capacity: 25, confidenceAvg: 0.0, activeSeen: 0 },
};

const apState = {
  "AP_01": "online",
  "AP_02": "online",
  "AP_03": "online",
};

// DOM Elements
const wsStatusBadge = document.getElementById("wsStatusBadge");
const wsStatusText = document.getElementById("wsStatusText");
const apStrip = document.getElementById("apStrip");
const eventFeed = document.getElementById("eventFeed");
const toastBanner = document.getElementById("toastBanner");
const toastText = document.getElementById("toastText");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initChart();
  setupFeedHover();
  fetchInitialData();
  connectWebSocket();
});

// ---------------------------------------------------------------------------
// 1. Initial REST Sync
// ---------------------------------------------------------------------------
async function fetchInitialData() {
  try {
    // Fetch rooms and APs
    const roomsRes = await fetch("/rooms");
    if (roomsRes.ok) {
      const roomsData = await roomsRes.json();
      renderApStrip(roomsData);
    }

    // Fetch initial occupancy
    const occRes = await fetch("/occupancy");
    if (occRes.ok) {
      const occData = await occRes.json();
      occData.forEach(updateRoomCard);
    }
  } catch (err) {
    console.warn("Could not fetch initial state via REST:", err);
  }
}

function renderApStrip(roomsData) {
  apStrip.innerHTML = '<span class="ap-strip-label">Access Points:</span>';
  roomsData.forEach(room => {
    (room.access_points || []).forEach(ap => {
      apState[ap.ap_id] = ap.status || "online";
      const pill = document.createElement("div");
      pill.id = `ap-pill-${ap.ap_id}`;
      pill.className = `ap-pill ${apState[ap.ap_id]}`;
      pill.innerHTML = `<span class="pulse-dot"></span> <strong>${ap.ap_id}</strong> (${room.room_id})`;
      pill.title = `Click to toggle ${ap.ap_id} (Simulate Outage)`;
      pill.onclick = () => toggleAp(ap.ap_id);
      apStrip.appendChild(pill);
    });
  });
}

// ---------------------------------------------------------------------------
// 2. Chart.js Initialization
// ---------------------------------------------------------------------------
function initChart() {
  const ctx = document.getElementById("occupancyChart").getContext("2d");

  occupancyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Room 101",
          borderColor: "#00f0ff",
          backgroundColor: "rgba(0, 240, 255, 0.08)",
          data: [],
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6,
        },
        {
          label: "Room 102",
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.08)",
          data: [],
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6,
        },
        {
          label: "Lab 1",
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.08)",
          data: [],
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#64748b", font: { family: "monospace", size: 10 } },
        },
        y: {
          min: 0,
          max: 100,
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: {
            color: "#64748b",
            font: { family: "monospace", size: 10 },
            callback: v => v + "%",
          },
        },
      },
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { family: "Inter", size: 11 } },
        },
        tooltip: {
          backgroundColor: "#0f172a",
          titleColor: "#f8fafc",
          bodyColor: "#94a3b8",
          borderColor: "#334155",
          borderWidth: 1,
          padding: 10,
        },
      },
    },
  });
}

function appendChartData(timeLabel, r101Occ, r102Occ, lab1Occ) {
  if (!occupancyChart) return;

  occupancyChart.data.labels.push(timeLabel);
  occupancyChart.data.datasets[0].data.push(r101Occ);
  occupancyChart.data.datasets[1].data.push(r102Occ);
  occupancyChart.data.datasets[2].data.push(lab1Occ);

  if (occupancyChart.data.labels.length > MAX_CHART_POINTS) {
    occupancyChart.data.labels.shift();
    occupancyChart.data.datasets.forEach(ds => ds.data.shift());
  }

  occupancyChart.update("none");
}

// ---------------------------------------------------------------------------
// 3. Circular Radial Gauge & Counter Animation
// ---------------------------------------------------------------------------
function updateRoomCard(data) {
  const roomId = data.room_id;
  const safeId = roomId.replace(/\s+/g, "_");

  const gaugeProgress = document.getElementById(`gauge-${safeId}`);
  const percentText = document.getElementById(`percent-${safeId}`);
  const estText = document.getElementById(`est-${safeId}`);
  const capText = document.getElementById(`cap-${safeId}`);
  const seenText = document.getElementById(`seen-${safeId}`);
  const confBadge = document.getElementById(`conf-${safeId}`);

  const pct = Math.min(100.0, Math.max(0.0, data.occupancy_pct || 0.0));
  const estimated = data.estimated_presence || 0;
  const capacity = data.capacity || 40;
  const confAvg = data.confidence_avg || 0.0;
  const activeSeen = data.active_devices || 0;

  // Update SVG radial progress (circumference = 314 for r=50)
  if (gaugeProgress) {
    const circumference = 314;
    const offset = circumference - (pct / 100.0) * circumference;
    gaugeProgress.style.strokeDashoffset = offset;

    // Color gradient based on occupancy load
    if (pct >= 85) gaugeProgress.style.stroke = "#f43f5e";
    else if (pct >= 60) gaugeProgress.style.stroke = "#00f0ff";
    else gaugeProgress.style.stroke = "#10b981";
  }

  // Animated numerical counter
  if (percentText) animateValue(percentText, parseFloat(percentText.innerText) || 0, pct, 500, 1);
  if (estText) estText.textContent = estimated;
  if (capText) capText.textContent = capacity;
  if (seenText) seenText.textContent = `${activeSeen} seen (${activeSeen - estimated} filtered noise)`;

  // Confidence badge
  if (confBadge) {
    const confPct = Math.round(confAvg * 100);
    if (confAvg >= 0.85) {
      confBadge.className = "confidence-badge confidence-high";
      confBadge.textContent = `High Conf (${confPct}%)`;
    } else if (confAvg >= 0.60) {
      confBadge.className = "confidence-badge confidence-medium";
      confBadge.textContent = `Med Conf (${confPct}%)`;
    } else {
      confBadge.className = "confidence-badge confidence-low";
      confBadge.textContent = `Low Conf (${confPct}%)`;
    }
  }

  // Update internal state
  if (roomState[roomId]) {
    roomState[roomId].occupancyPct = pct;
    roomState[roomId].estimated = estimated;
    roomState[roomId].confidenceAvg = confAvg;
    roomState[roomId].activeSeen = activeSeen;
  }
}

function animateValue(element, start, end, duration, decimals = 0) {
  if (start === end) return;
  const range = end - start;
  let current = start;
  const increment = end > start ? 1 : -1;
  const stepTime = Math.abs(Math.floor(duration / 30));
  const startTime = performance.now();

  function update() {
    const elapsed = performance.now() - startTime;
    const progress = Math.min(1.0, elapsed / duration);
    current = start + range * progress;
    element.textContent = current.toFixed(decimals);

    if (progress < 1.0) {
      requestAnimationFrame(update);
    } else {
      element.textContent = end.toFixed(decimals);
    }
  }
  requestAnimationFrame(update);
}

// ---------------------------------------------------------------------------
// 4. Live Event Ticker Feed
// ---------------------------------------------------------------------------
function setupFeedHover() {
  eventFeed.addEventListener("mouseenter", () => { isFeedHovered = true; });
  eventFeed.addEventListener("mouseleave", () => { isFeedHovered = false; });
}

function appendEventToFeed(ev) {
  const row = document.createElement("div");
  row.className = "event-row";

  const timeStr = ev.timestamp ? ev.timestamp.split("T")[1]?.slice(0, 8) || ev.timestamp : "--:--:--";
  const eventType = ev.event || "ping";
  const rssi = parseInt(ev.rssi) || -50;

  let typeClass = "event-type-heartbeat";
  if (eventType === "connect") typeClass = "event-type-connect";
  else if (eventType === "disconnect") typeClass = "event-type-disconnect";

  let rssiClass = "rssi-strong";
  if (rssi < -70) rssiClass = "rssi-weak";
  else if (rssi < -55) rssiClass = "rssi-medium";

  row.innerHTML = `
    <div>${timeStr}</div>
    <div><strong>${ev.ap_id}</strong></div>
    <div>${ev.device_id}</div>
    <div class="${typeClass}">${eventType.toUpperCase()}</div>
    <div class="rssi-pill ${rssiClass}">${rssi} dBm</div>
  `;

  eventFeed.insertBefore(row, eventFeed.firstChild);

  // Maintain bounded feed size
  if (eventFeed.children.length > MAX_FEED_ITEMS) {
    eventFeed.removeChild(eventFeed.lastChild);
  }

  // Auto-scroll to top unless hovered
  if (!isFeedHovered) {
    eventFeed.scrollTop = 0;
  }
}

// ---------------------------------------------------------------------------
// 5. WebSocket Lifecycle
// ---------------------------------------------------------------------------
let wsInstance = null;
let reconnectTimer = null;

function connectWebSocket() {
  if (wsInstance && wsInstance.readyState === WebSocket.OPEN) return;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.hostname || "localhost";
  const port = window.location.port ? `:${window.location.port}` : ":8000";
  const wsUrl = `${protocol}//${host}${port}/live`;

  wsInstance = new WebSocket(wsUrl);

  wsInstance.onopen = () => {
    wsStatusBadge.className = "status-badge status-connected";
    wsStatusText.textContent = "NOC LIVE";
    hideToast();
    if (reconnectTimer) {
      clearInterval(reconnectTimer);
      reconnectTimer = null;
    }
  };

  wsInstance.onmessage = (msg) => {
    try {
      const payload = JSON.parse(msg.data);

      if (payload.type === "event") {
        appendEventToFeed(payload);

        // If occupancy updated for room, refresh card & chart
        if (payload.room_occupancy) {
          updateRoomCard(payload.room_occupancy);

          const timeStr = payload.timestamp ? payload.timestamp.split("T")[1]?.slice(0, 8) : "";
          appendChartData(
            timeStr,
            roomState["Room 101"].occupancyPct,
            roomState["Room 102"].occupancyPct,
            roomState["Lab 1"].occupancyPct
          );
        }
      } else if (payload.type === "ap_status_update") {
        const apPill = document.getElementById(`ap-pill-${payload.ap_id}`);
        if (apPill) {
          apPill.className = `ap-pill ${payload.status}`;
        }
        showToast(`AP status changed: ${payload.ap_id} -> ${payload.status.toUpperCase()}`);
      }
    } catch (e) {
      console.error("Error handling WS message:", e);
    }
  };

  wsInstance.onclose = () => {
    wsStatusBadge.className = "status-badge status-disconnected";
    wsStatusText.textContent = "DISCONNECTED";
    showToast("WebSocket disconnected. Auto-reconnecting in 2s...");
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(connectWebSocket, 2000);
    }
  };

  wsInstance.onerror = (err) => {
    console.warn("WebSocket encountered error:", err);
    wsInstance.close();
  };
}

// ---------------------------------------------------------------------------
// 6. Interactive Demo Controls
// ---------------------------------------------------------------------------
async function triggerSimulateEntry() {
  try {
    const res = await fetch("/demo/simulate-entry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room_id: "Room 101" }),
    });
    if (res.ok) {
      showToast("Simulated device entry into Room 101");
    }
  } catch (err) {
    showToast(`Error simulating entry: ${err.message}`);
  }
}

async function triggerSimulateExit() {
  try {
    const res = await fetch("/demo/simulate-exit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room_id: "Room 101" }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.status === "no_active_devices") {
        showToast("No active devices in Room 101 to exit.");
      } else {
        showToast(`Simulated device exit from Room 101`);
      }
    }
  } catch (err) {
    showToast(`Error simulating exit: ${err.message}`);
  }
}

async function toggleAp(apId = "AP_01") {
  try {
    const res = await fetch("/demo/toggle-ap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ap_id: apId }),
    });
    if (res.ok) {
      const data = await res.json();
      showToast(`Toggled ${data.ap_id} to ${data.current_status.toUpperCase()}`);
    }
  } catch (err) {
    showToast(`Error toggling AP: ${err.message}`);
  }
}

async function triggerScenario(scenarioName) {
  try {
    showToast(`Starting scenario '${scenarioName}' (40x speed)...`);
    const res = await fetch("/demo/run-scenario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: scenarioName, speed: 40.0 }),
    });
    if (res.ok) {
      showToast(`Scenario '${scenarioName}' streaming live!`);
    }
  } catch (err) {
    showToast(`Error running scenario: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// 7. Toast Notifications
// ---------------------------------------------------------------------------
let toastTimeout = null;

function showToast(text) {
  toastText.textContent = text;
  toastBanner.style.display = "flex";
  if (toastTimeout) clearTimeout(toastTimeout);
  toastTimeout = setTimeout(hideToast, 4000);
}

function hideToast() {
  toastBanner.style.display = "none";
}
