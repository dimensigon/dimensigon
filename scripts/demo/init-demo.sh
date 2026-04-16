#!/bin/bash
# Initialize the demo cluster: wait for all nodes, set granules, load sample data.
# Called by reset-demo.sh after docker compose up.

set -e

MASTER_URL="https://localhost:20194"
CURL_OPTS="-sfk"
PASSWORD="demo123"
MAX_WAIT=120

echo "[$(date)] === DEMO CLUSTER INIT ==="

# ── Wait for master ──────────────────────────────
echo "[init] Waiting for dm-master..."
for i in $(seq 1 $MAX_WAIT); do
    if curl -sfk "$MASTER_URL/healthcheck" > /dev/null 2>&1; then
        echo "[init] dm-master is ready."
        break
    fi
    sleep 2
done

# ── Login ────────────────────────────────────────
echo "[init] Logging in..."
TOKEN=$(curl -sfk "$MASTER_URL/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"root\", \"password\": \"$PASSWORD\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null) || true

if [ -z "$TOKEN" ]; then
    echo "[init] WARNING: Could not login. Cluster may not be fully initialized."
    exit 0
fi

AUTH="Authorization: Bearer $TOKEN"

# ── Wait for all nodes ───────────────────────────
echo "[init] Waiting for all 5 nodes to join..."
for i in $(seq 1 60); do
    NODE_COUNT=$(curl -sfk "$MASTER_URL/healthcheck" \
        -H "$AUTH" -H "D-Securizer: plain" | python3 -c "
import sys,json
d=json.load(sys.stdin)
neighbours = d.get('neighbours', [])
print(len(neighbours) + 1)
" 2>/dev/null) || NODE_COUNT=0

    if [ "$NODE_COUNT" -ge 5 ]; then
        echo "[init] All 5 nodes online."
        break
    fi
    echo "[init]   $NODE_COUNT/5 nodes online, waiting..."
    sleep 5
done

# ── Load sample action templates ─────────────────
echo "[init] Loading sample action templates..."

curl -sfk -X POST "$MASTER_URL/api/v1.0/action_templates" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "check-disk-usage",
        "action_type": "SHELL",
        "code": "df -h / | awk '\''NR==2{usage=$5+0; if(usage > 90) {print \"CRITICAL: \" usage \"%\"; exit 1} else {print \"OK: \" usage \"%\"}}'\''",
        "expected_rc": 0,
        "description": "Check disk usage and fail if root partition exceeds 90%"
    }' > /dev/null 2>&1 && echo "  + check-disk-usage" || echo "  ~ check-disk-usage (may exist)"

curl -sfk -X POST "$MASTER_URL/api/v1.0/action_templates" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "check-memory",
        "action_type": "SHELL",
        "code": "free -m | awk '\''NR==2{usage=$3/$2*100; if(usage > 85) {printf \"WARN: %.0f%%\\n\", usage; exit 1} else {printf \"OK: %.0f%%\\n\", usage}}'\''",
        "expected_rc": 0,
        "description": "Check memory usage and warn if above 85%"
    }' > /dev/null 2>&1 && echo "  + check-memory" || echo "  ~ check-memory (may exist)"

curl -sfk -X POST "$MASTER_URL/api/v1.0/action_templates" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "system-uptime",
        "action_type": "SHELL",
        "code": "uptime -p",
        "expected_rc": 0,
        "description": "Show system uptime in human-readable format"
    }' > /dev/null 2>&1 && echo "  + system-uptime" || echo "  ~ system-uptime (may exist)"

curl -sfk -X POST "$MASTER_URL/api/v1.0/action_templates" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "list-processes",
        "action_type": "SHELL",
        "code": "ps aux --sort=-%mem | head -10",
        "expected_rc": 0,
        "description": "List top 10 processes by memory usage"
    }' > /dev/null 2>&1 && echo "  + list-processes" || echo "  ~ list-processes (may exist)"

curl -sfk -X POST "$MASTER_URL/api/v1.0/action_templates" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "network-connections",
        "action_type": "SHELL",
        "code": "ss -tlnp | head -20",
        "expected_rc": 0,
        "description": "Show listening TCP ports and associated processes"
    }' > /dev/null 2>&1 && echo "  + network-connections" || echo "  ~ network-connections (may exist)"

# ── Load sample orchestrations ───────────────────
echo "[init] Loading sample orchestrations..."

curl -sfk -X POST "$MASTER_URL/api/v1.0/orchestrations/full" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "health-check-all-nodes",
        "description": "Run health checks (disk, memory, uptime) across all nodes in parallel",
        "stop_on_error": false,
        "steps": [
            {"id": "1", "undo": false, "name": "check-disk", "action_type": "SHELL",
             "code": "df -h / | tail -1", "target": "all", "parent_step_ids": []},
            {"id": "2", "undo": false, "name": "check-memory", "action_type": "SHELL",
             "code": "free -m | awk '\''NR==2{printf \"%.0f%% used\\n\", $3/$2*100}'\''", "target": "all", "parent_step_ids": []},
            {"id": "3", "undo": false, "name": "check-uptime", "action_type": "SHELL",
             "code": "uptime -p", "target": "all", "parent_step_ids": []},
            {"id": "4", "undo": false, "name": "summary", "action_type": "SHELL",
             "code": "echo \"Health check complete on $(hostname)\"", "target": "all", "parent_step_ids": ["1","2","3"]}
        ]
    }' > /dev/null 2>&1 && echo "  + health-check-all-nodes" || echo "  ~ health-check-all-nodes (may exist)"

curl -sfk -X POST "$MASTER_URL/api/v1.0/orchestrations/full" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "security-audit-mesh",
        "description": "Run security checks across all mesh nodes: SSH config, open ports, updates",
        "stop_on_error": false,
        "steps": [
            {"id": "1", "undo": false, "name": "check-ssh-config", "action_type": "SHELL",
             "code": "grep -q \"PermitRootLogin\" /etc/ssh/sshd_config 2>/dev/null && echo \"SSH config: found\" || echo \"SSH config: not found\"",
             "target": "all", "parent_step_ids": []},
            {"id": "2", "undo": false, "name": "check-open-ports", "action_type": "SHELL",
             "code": "ss -tlnp | wc -l", "target": "all", "parent_step_ids": []},
            {"id": "3", "undo": false, "name": "check-hostname", "action_type": "SHELL",
             "code": "hostname && whoami", "target": "all", "parent_step_ids": []},
            {"id": "4", "undo": false, "name": "audit-report", "action_type": "SHELL",
             "code": "echo \"Audit complete on $(hostname) at $(date)\"",
             "target": "all", "parent_step_ids": ["1","2","3"]}
        ]
    }' > /dev/null 2>&1 && echo "  + security-audit-mesh" || echo "  ~ security-audit-mesh (may exist)"

curl -sfk -X POST "$MASTER_URL/api/v1.0/orchestrations/full" \
    -H "$AUTH" -H "Content-Type: application/json" -H "D-Securizer: plain" \
    -d '{
        "name": "web-servers-report",
        "description": "Gather system info from web-tier servers only (granule: web)",
        "stop_on_error": false,
        "steps": [
            {"id": "1", "undo": false, "name": "web-disk-check", "action_type": "SHELL",
             "code": "echo \"=== $(hostname) ===\"; df -h / | tail -1",
             "target": ["web"], "parent_step_ids": []},
            {"id": "2", "undo": false, "name": "web-load-check", "action_type": "SHELL",
             "code": "cat /proc/loadavg",
             "target": ["web"], "parent_step_ids": []},
            {"id": "3", "undo": false, "name": "web-summary", "action_type": "SHELL",
             "code": "echo \"Web node $(hostname) report complete\"",
             "target": ["web"], "parent_step_ids": ["1","2"]}
        ]
    }' > /dev/null 2>&1 && echo "  + web-servers-report" || echo "  ~ web-servers-report (may exist)"

echo "[$(date)] === DEMO CLUSTER INIT COMPLETE ==="
echo "[init] Nodes: $NODE_COUNT/5"
echo "[init] Ready at: $MASTER_URL/healthcheck?human"
