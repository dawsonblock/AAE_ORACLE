# =============================================================================
# Dockerfile — AAE (Autonomous Agent Engineering) Platform
# Multi-stage: builder → runtime → dev
# =============================================================================

# ---- Stage 1: builder -------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for layer caching
COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="AAE Platform" \
      org.opencontainers.image.description="Autonomous Agent Engineering Platform" \
      org.opencontainers.image.version="2.0.0"

# Runtime system deps (git for patch apply, procps for signal handling)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        procps \
        patch \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd --gid 1001 aae && \
    useradd --uid 1001 --gid aae --shell /bin/bash --create-home aae

WORKDIR /app

# Copy application source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY configs/ ./configs/

# Ensure scripts are executable
RUN chmod +x scripts/*.py

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO

USER aae

# Default: run the gateway API server
CMD ["python", "-m", "uvicorn", "aae.gateway.api_server:app", \
     "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# ---- Stage 3: dev (adds test deps + shell tools) ----------------------------
FROM runtime AS dev

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        vim \
        less \
        jq \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
        pytest \
        pytest-asyncio \
        pytest-cov \
        httpx \
        mypy \
        ruff

COPY tests/ ./tests/

USER aae

CMD ["bash"]
