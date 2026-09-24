# ==============================================================================
# Production Dockerfile for Wi-Fi Presence Estimation System
# ==============================================================================

FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    ENVIRONMENT=production

# Install system utilities (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Set working directory
WORKDIR /app

# Install Python dependencies first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=appuser:appgroup . /app

# Ensure writable directories for database & data artifacts exist
RUN mkdir -p /app/database /app/data && \
    chown -R appuser:appgroup /app/database /app/data && \
    chmod +x /app/docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Expose FastAPI application port
EXPOSE 8000

# Docker healthcheck endpoint validation
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint initializes database and starts application
ENTRYPOINT ["/app/docker-entrypoint.sh"]
