#!/bin/bash
# One-command runner for the Wi-Fi Presence system

set -e

echo "========================================="
echo " Starting Wi-Fi Presence System"
echo "========================================="

# Ensure we're in the project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check if port 8000 is in use, and try to kill it if it's a dev server
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "[!] Port 8000 is already in use. Attempting to free it..."
    lsof -Pi :8000 -sTCP:LISTEN -t | xargs kill -9 || true
    sleep 1
fi

echo "[+] Starting FastAPI backend on port 8000..."
python3 backend/main.py &
BACKEND_PID=$!

echo "[+] Waiting for backend to initialize..."
sleep 3

echo "[+] Opening Live NOC Dashboard in browser..."
# macOS: open, Linux: xdg-open, Windows: start
if command -v open > /dev/null; then
    open http://localhost:8000/
elif command -v xdg-open > /dev/null; then
    xdg-open http://localhost:8000/
else
    echo "Could not open browser automatically. Please navigate to http://localhost:8000/"
fi

echo "========================================="
echo " System is running! (PID: $BACKEND_PID)"
echo " To run the live demo script:"
echo "   python3 simulator/demo_script.py"
echo ""
echo " Press Ctrl+C to stop the server."
echo "========================================="

# Wait for backend process to finish (or Ctrl+C)
wait $BACKEND_PID
