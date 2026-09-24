#!/bin/bash
# ==============================================================================
# Automated Production Deployment Script
# ==============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." &> /dev/null && pwd )"
cd "$PROJECT_ROOT"

echo "========================================================"
echo " Deploying Wi-Fi Presence Estimation System"
echo "========================================================"

# Step 1: Run automated test suite
echo "[+] Step 1: Running test suite before deployment..."
pytest -q

# Step 2: Ensure database backup before rolling update
if [ -f "deploy/scripts/backup_db.sh" ]; then
    echo "[+] Step 2: Creating database backup..."
    bash deploy/scripts/backup_db.sh || echo "[!] Warning: Backup script failed, continuing..."
fi

# Step 3: Build & restart containers
echo "[+] Step 3: Building and deploying Docker containers..."
if [ -f "docker-compose.prod.yml" ] && [ "$1" == "--prod" ]; then
    docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
else
    docker compose up -d --build --remove-orphans
fi

# Step 4: Validate deployment health check
echo "[+] Step 4: Verifying health status..."
RETRIES=10
DELAY=3
HEALTH_URL="http://localhost:8000/health"

for i in $(seq 1 $RETRIES); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true)
    if [ "$HTTP_CODE" == "200" ]; then
        echo "[✓] Deployment healthy! Service responded with HTTP 200."
        exit 0
    fi
    echo "    Waiting for service to be healthy (attempt $i/$RETRIES, status: $HTTP_CODE)..."
    sleep $DELAY
done

echo "[!] Error: Health check failed after deployment."
exit 1
