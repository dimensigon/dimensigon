# Multi-stage Dockerfile for Dimensigon 2.0 Production Deployment
# Optimized for security, size, and performance

# Build argument for Python version
ARG PYTHON_VERSION=3.11

# ============================================================================
# Stage 1: Builder - Compile dependencies and prepare application
# ============================================================================
FROM python:${PYTHON_VERSION}-slim as builder

LABEL stage=builder
LABEL maintainer="Joan Prat <joan.prat@dimensigon.com>"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    libssl-dev \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /build

# Copy only requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies to a temporary directory
# This allows us to copy only the installed packages to the final image
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install --no-warn-script-location \
    -r requirements.txt

# Copy application source code
COPY dimensigon/ ./dimensigon/
COPY templates/ ./templates/
COPY plugins/ ./plugins/
COPY setup.py README.md ./

# Install Dimensigon in the /install directory
RUN pip install --no-cache-dir --prefix=/install --no-warn-script-location -e .

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:${PYTHON_VERSION}-slim

LABEL org.opencontainers.image.title="Dimensigon"
LABEL org.opencontainers.image.description="Distributed Orchestration Platform with Mesh Networking"
LABEL org.opencontainers.image.version="2.0.0"
LABEL org.opencontainers.image.vendor="Dimensigon"
LABEL org.opencontainers.image.authors="Joan Prat <joan.prat@dimensigon.com>"
LABEL org.opencontainers.image.url="https://github.com/dimensigon/dimensigon"
LABEL org.opencontainers.image.documentation="https://github.com/dimensigon/dimensigon/blob/master/README.md"
LABEL org.opencontainers.image.source="https://github.com/dimensigon/dimensigon"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libssl3 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user and group for security
RUN groupadd -r -g 1000 dimensigon && \
    useradd -r -u 1000 -g dimensigon -m -d /home/dimensigon -s /bin/bash dimensigon

# Set working directory
WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application files
COPY --from=builder /build/dimensigon ./dimensigon/
COPY --from=builder /build/templates ./templates/
COPY --from=builder /build/setup.py /build/README.md ./

# Create necessary directories with proper permissions
RUN mkdir -p \
    /app/.dimensigon/.ssl \
    /app/data \
    /var/log/dimensigon \
    /app/logs \
    && chown -R dimensigon:dimensigon /app /var/log/dimensigon

# Switch to non-root user
USER dimensigon

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    PATH="/home/dimensigon/.local/bin:${PATH}"

# Set Flask application
ENV FLASK_APP=dimensigon.web

# Set default configuration directory
ENV CONFIG_DIR=/app/.dimensigon

# Expose default Dimensigon port
EXPOSE 20194

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:20194/health', timeout=5)" || exit 1

# Volume for persistent data
VOLUME ["/app/.dimensigon", "/app/data", "/var/log/dimensigon"]

# Entry point script for flexible startup
COPY docker-entrypoint.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
USER dimensigon

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command: Start Gunicorn with production settings
CMD ["gunicorn", \
     "--bind", "0.0.0.0:20194", \
     "--workers", "4", \
     "--threads", "2", \
     "--worker-class", "sync", \
     "--worker-tmp-dir", "/dev/shm", \
     "--timeout", "120", \
     "--keepalive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "--capture-output", \
     "--enable-stdio-inheritance", \
     "dimensigon.web:create_app('production')"]
