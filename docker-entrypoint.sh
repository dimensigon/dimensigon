#!/bin/bash
# Dimensigon Docker Entrypoint Script
# Handles initialization, SSL certificates, and flexible command execution

set -e

# Color output for better visibility
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
CONFIG_DIR="${CONFIG_DIR:-/app/.dimensigon}"
SSL_DIR="${CONFIG_DIR}/.ssl"
CERT_FILE="${SSL_DIR}/cert.pem"
KEY_FILE="${SSL_DIR}/key.pem"

log_info "Starting Dimensigon 2.0..."
log_info "Configuration directory: ${CONFIG_DIR}"

# Ensure directories exist
mkdir -p "${SSL_DIR}" /app/data /var/log/dimensigon

# Check for SSL certificates
if [ ! -f "${CERT_FILE}" ] || [ ! -f "${KEY_FILE}" ]; then
    log_warn "SSL certificates not found. Generating self-signed certificate..."

    # Generate self-signed certificate
    openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
        -keyout "${KEY_FILE}" \
        -out "${CERT_FILE}" \
        -subj "/C=US/ST=State/L=City/O=Dimensigon/OU=IT/CN=dimensigon.local" \
        2>/dev/null

    chmod 600 "${KEY_FILE}"
    chmod 644 "${CERT_FILE}"

    log_info "Self-signed certificate generated successfully"
else
    log_info "SSL certificates found"
fi

# Validate SSL certificates
if openssl x509 -checkend 86400 -noout -in "${CERT_FILE}" >/dev/null 2>&1; then
    log_info "SSL certificate is valid"
else
    log_warn "SSL certificate expires within 24 hours or is invalid"
fi

# Set environment defaults if not provided
export FLASK_CONFIG="${FLASK_CONFIG:-production}"
export FLASK_APP="${FLASK_APP:-dimensigon.web}"
export DM_PORT="${DM_PORT:-20194}"
export WORKERS="${WORKERS:-4}"
export GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"

log_info "Environment configuration:"
log_info "  - FLASK_CONFIG: ${FLASK_CONFIG}"
log_info "  - DM_PORT: ${DM_PORT}"
log_info "  - WORKERS: ${WORKERS}"
log_info "  - Database: ${SQLALCHEMY_DATABASE_URI%%@*}@***"

# Wait for database to be ready (if PostgreSQL)
if [[ "${SQLALCHEMY_DATABASE_URI}" == postgresql* ]]; then
    log_info "Waiting for PostgreSQL database..."

    # Extract database host and port from connection string
    DB_HOST=$(echo "${SQLALCHEMY_DATABASE_URI}" | sed -n 's/.*@\([^:]*\).*/\1/p')
    DB_PORT=$(echo "${SQLALCHEMY_DATABASE_URI}" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT="${DB_PORT:-5432}"

    max_attempts=30
    attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if nc -z "${DB_HOST}" "${DB_PORT}" 2>/dev/null; then
            log_info "Database is ready!"
            break
        fi

        attempt=$((attempt + 1))
        log_warn "Database not ready yet (attempt ${attempt}/${max_attempts}). Waiting..."
        sleep 2
    done

    if [ $attempt -eq $max_attempts ]; then
        log_error "Database connection timeout!"
        exit 1
    fi
fi

# Initialize dimension if needed (check environment variable)
if [ "${DIMENSIGON_INIT_NEW}" = "true" ] && [ -n "${DIMENSION_NAME}" ]; then
    log_info "Initializing new dimension: ${DIMENSION_NAME}"
    dimensigon new "${DIMENSION_NAME}"
fi

# Join dimension if token provided
if [ "${DIMENSIGON_JOIN}" = "true" ] && [ -n "${JOIN_SERVER}" ] && [ -n "${JOIN_TOKEN}" ]; then
    log_info "Joining dimension at ${JOIN_SERVER}"
    dimensigon join "${JOIN_SERVER}" "${JOIN_TOKEN}" \
        --port "${JOIN_PORT:-20194}" \
        ${JOIN_SSL:+--ssl} \
        ${JOIN_VERIFY:+--verify}
fi

# Handle special commands
case "${1}" in
    bash|sh)
        log_info "Starting interactive shell"
        exec "$@"
        ;;

    dimensigon)
        log_info "Executing Dimensigon command: ${*}"
        exec "$@"
        ;;

    gunicorn)
        log_info "Starting Gunicorn with ${WORKERS} workers"
        exec "$@"
        ;;

    test)
        log_info "Running tests"
        exec pytest tests/
        ;;

    *)
        # Default: Start gunicorn if no command provided
        if [ $# -eq 0 ]; then
            log_info "Starting Dimensigon with Gunicorn (${WORKERS} workers)"
            exec gunicorn \
                --bind "0.0.0.0:${DM_PORT}" \
                --workers "${WORKERS}" \
                --threads 2 \
                --worker-class sync \
                --worker-tmp-dir /dev/shm \
                --timeout "${GUNICORN_TIMEOUT}" \
                --keepalive 5 \
                --max-requests 1000 \
                --max-requests-jitter 100 \
                --access-logfile - \
                --error-logfile - \
                --log-level "${LOG_LEVEL:-info}" \
                --capture-output \
                --enable-stdio-inheritance \
                "dimensigon.web:create_app('${FLASK_CONFIG}')"
        else
            log_info "Executing command: $*"
            exec "$@"
        fi
        ;;
esac
