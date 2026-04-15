# =============================================================================
# HORRORBOT API - Dockerfile
# =============================================================================
# FastAPI backend with ML models (LLM, embeddings, classifier)
#
# Build:  docker compose build api
# Run:    docker compose up -d api
# Logs:   docker compose logs -f api
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# ── System dependencies ──────────────────────────────────────────────────────
# libpq-dev: psycopg2, build-essential+cmake: llama-cpp-python fallback build,
# curl: healthcheck, openjdk-21-jre-headless: pyspark runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev \
        build-essential \
        cmake \
        curl \
        musl \
        openjdk-21-jre-headless \
    && ln -sf /usr/lib/x86_64-linux-musl/libc.so /usr/lib/libc.musl-x86_64.so.1 \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# ── Install uv ──────────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# ── Dependencies (cached layer) ─────────────────────────────────────────────
COPY pyproject.toml uv.lock README.md ./
# Install deps + download Playwright chromium (needed by RT scraper) in one layer
RUN uv sync --frozen --group ml-api && \
    uv run playwright install --with-deps chromium

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
