# =============================================================================
# HORRORBOT API - Dockerfile
# =============================================================================
# FastAPI backend with ML models (LLM, embeddings, classifier).
#
# Scope: API runtime only. ETL pipelines (Spark, Playwright/Rotten Tomatoes
# scraping) are executed offline and excluded from this image to minimize
# CVE surface and image size.
#
# Build:  docker compose build api
# Run:    docker compose up -d api
# Logs:   docker compose logs -f api
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# ── System dependencies ──────────────────────────────────────────────────────
# libpq-dev        : psycopg2 build headers
# build-essential  : llama-cpp-python fallback build (wheel preferred)
# cmake            : llama-cpp-python fallback build
# curl             : healthcheck
# musl             : required by llama-cpp-python CPU wheels (linked to musl libc)
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        build-essential \
        cmake \
        curl \
        musl \
    && ln -sf /usr/lib/x86_64-linux-musl/libc.so /usr/lib/libc.musl-x86_64.so.1 \
    && rm -rf /var/lib/apt/lists/*

# ── Install uv ──────────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# ── Dependencies (cached layer) ─────────────────────────────────────────────
# Only the ml-api group is installed (no pyspark, no playwright).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --group ml-api

# ── Application code ─────────────────────────────────────────────────────────
COPY src/ src/

# ── Runtime config ───────────────────────────────────────────────────────────
# CPU-only inference
ENV LLM_N_GPU_LAYERS=0
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=30 --start-period=480s \
    CMD curl -f http://localhost:8000/api/docs || exit 1

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]