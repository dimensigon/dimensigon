#!/bin/bash
# Reset the Dimensigon demo cluster.
# Destroys all containers/volumes and recreates from scratch.
# Cron: 0 3 * * * /home/app/dimensigon/scripts/demo/reset-demo.sh >> /var/log/demo-reset.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.demo.yml"

echo ""
echo "========================================"
echo "  DEMO CLUSTER RESET - $(date)"
echo "========================================"

# Step 1: Tear down
echo "[reset] Stopping and removing containers..."
cd "$PROJECT_DIR"
docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>&1 || true
sleep 5

# Step 2: Rebuild and start
echo "[reset] Building and starting fresh cluster..."
docker compose -f "$COMPOSE_FILE" build --quiet 2>&1 || true
docker compose -f "$COMPOSE_FILE" up -d 2>&1

# Step 3: Wait for master to be healthy
echo "[reset] Waiting for dm-master to be healthy..."
for i in $(seq 1 90); do
    if curl -sf http://localhost:20194/healthcheck > /dev/null 2>&1; then
        echo "[reset] dm-master is up after ${i}0 seconds"
        break
    fi
    sleep 10
done

# Step 4: Wait for all nodes to join (up to 5 minutes)
echo "[reset] Waiting for all nodes to join..."
sleep 60

# Step 5: Load sample data
echo "[reset] Loading demo data..."
bash "$SCRIPT_DIR/init-demo.sh"

echo ""
echo "[reset] Demo cluster reset complete at $(date)"
echo "========================================"
