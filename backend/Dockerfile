# =============================================================================
# Energize Backend — multi-stage Docker image
#
# Stage 1 (builder)  installs all Python packages inside a virtual-env.
#                    Needs build-essential + gcc so that packages with C
#                    extensions (grpcio, cryptography, asyncpg, etc.) can
#                    compile when a pre-built wheel is unavailable.
#
# Stage 2 (runtime)  copies only the compiled venv — no compiler toolchain.
#                    curl is added for the docker-compose healthcheck.
# =============================================================================

# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create an isolated virtual environment so Stage 2 can simply copy it.
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"
ENV VIRTUAL_ENV=/venv

RUN pip install --upgrade --no-cache-dir pip uv

COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

# curl is used by the docker-compose healthcheck (GET /health).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

COPY . .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
