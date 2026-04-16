#!/bin/bash
# Initialize a DM dimension for testing.
# Called by the container entrypoint.

set -e

DM_PORT="${DM_PORT:-20194}"
DM_DIMENSION_NAME="${DM_DIMENSION_NAME:-test-dimension}"
DM_ROOT_PASSWORD="${DM_ROOT_PASSWORD:-testpass123}"

echo "[init] Waiting for DM to be ready..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${DM_PORT}/" > /dev/null 2>&1; then
        echo "[init] DM is ready."
        break
    fi
    sleep 1
done

if [ -n "${DM_INIT_NEW}" ]; then
    echo "[init] Creating new dimension: ${DM_DIMENSION_NAME}"
    # The DM CLI handles dimension creation
    python -m dimensigon new "${DM_DIMENSION_NAME}" --password "${DM_ROOT_PASSWORD}" 2>/dev/null || true
fi

if [ -n "${DM_JOIN_SERVER}" ]; then
    echo "[init] Joining dimension at ${DM_JOIN_SERVER}:${DM_JOIN_PORT:-20194}"

    # Get join token from master
    TOKEN=$(curl -sf "http://${DM_JOIN_SERVER}:${DM_JOIN_PORT:-20194}/api/v1.0/join/token" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"root\", \"password\": \"${DM_ROOT_PASSWORD}\"}" \
        | jq -r '.token' 2>/dev/null) || true

    if [ -n "${TOKEN}" ] && [ "${TOKEN}" != "null" ]; then
        python -m dimensigon join "${DM_JOIN_SERVER}" "${TOKEN}" \
            --port "${DM_JOIN_PORT:-20194}" \
            --no-ssl 2>/dev/null || true
    else
        echo "[init] Warning: Could not obtain join token"
    fi
fi

# Set granules if specified
if [ -n "${DM_GRANULES}" ]; then
    echo "[init] Setting granules: ${DM_GRANULES}"
    IFS=',' read -ra GRANULE_ARRAY <<< "${DM_GRANULES}"
    GRANULE_JSON=$(printf '%s\n' "${GRANULE_ARRAY[@]}" | jq -R . | jq -s .)

    # Login and set granules
    AUTH_TOKEN=$(curl -sf "http://localhost:${DM_PORT}/api/v1.0/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"root\", \"password\": \"${DM_ROOT_PASSWORD}\"}" \
        | jq -r '.access_token' 2>/dev/null) || true

    if [ -n "${AUTH_TOKEN}" ] && [ "${AUTH_TOKEN}" != "null" ]; then
        # Get current server ID
        SERVER_ID=$(curl -sf "http://localhost:${DM_PORT}/api/v1.0/servers" \
            -H "Authorization: Bearer ${AUTH_TOKEN}" \
            | jq -r '.[0].id' 2>/dev/null) || true

        if [ -n "${SERVER_ID}" ] && [ "${SERVER_ID}" != "null" ]; then
            curl -sf -X PATCH "http://localhost:${DM_PORT}/api/v1.0/servers/${SERVER_ID}" \
                -H "Authorization: Bearer ${AUTH_TOKEN}" \
                -H "Content-Type: application/json" \
                -d "{\"granules\": ${GRANULE_JSON}}" 2>/dev/null || true
            echo "[init] Granules set successfully"
        fi
    fi
fi

echo "[init] Initialization complete."
