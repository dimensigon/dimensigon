#!/bin/bash
# Demo node startup script - handles dimension creation/joining and starts DM
set -e

DM_PORT="${DM_PORT:-20194}"
MASTER="${DM_JOIN_SERVER:-dm-master}"
MASTER_PORT="${DM_JOIN_PORT:-20194}"
MASTER_URL="https://${MASTER}:${MASTER_PORT}"
PASSWORD="${DM_ROOT_PASSWORD:-demo123}"

echo "[demo] Starting Dimensigon demo node..."

# Create new dimension if configured (master only)
if [ "${DIMENSIGON_INIT_NEW}" = "true" ] && [ -n "${DIMENSION_NAME}" ]; then
    echo "[demo] Creating dimension: ${DIMENSION_NAME}"
    echo -e "${PASSWORD}\n${PASSWORD}" | dimensigon new "${DIMENSION_NAME}" 2>&1 || echo "[demo] Dimension may already exist"
fi

# Join existing dimension if configured (workers)
if [ -n "${DM_JOIN_SERVER}" ]; then
    echo "[demo] Waiting for master at ${MASTER_URL}..."
    for i in $(seq 1 120); do
        if curl -sfk "${MASTER_URL}/" > /dev/null 2>&1; then
            echo "[demo] Master is reachable"
            break
        fi
        sleep 3
    done

    echo "[demo] Logging in to master..."
    TOKEN=$(curl -sfk "${MASTER_URL}/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"root\",\"password\":\"${PASSWORD}\"}" \
        2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null) || true

    if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
        echo "[demo] Login OK, requesting join token..."
        JOIN_TOKEN=$(curl -sfk "${MASTER_URL}/api/v1.0/join/token" \
            -H "Authorization: Bearer $TOKEN" \
            -H "D-Securizer: plain" \
            -H "Content-Type: application/json" \
            2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null) || true

        if [ -n "$JOIN_TOKEN" ] && [ "$JOIN_TOKEN" != "" ]; then
            echo "[demo] Got join token, joining dimension..."
            dimensigon join "${MASTER}" "$JOIN_TOKEN" --port "${MASTER_PORT}" 2>&1 || echo "[demo] Join may have already completed"
        else
            echo "[demo] Could not get join token from API"
            # Try using dimensigon token command format
            echo "[demo] Attempting direct join..."
            dimensigon join "${MASTER}" "dummy" --port "${MASTER_PORT}" 2>&1 || echo "[demo] Direct join failed"
        fi
    else
        echo "[demo] Could not login to master (token empty)"
    fi
fi

echo "[demo] Starting Dimensigon server on port ${DM_PORT}..."
exec dimensigon --port "${DM_PORT}"
