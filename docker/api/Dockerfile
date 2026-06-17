# =============================================================================
# HORRORBOT API - Dockerfile (GPU / CUDA build)
# =============================================================================
# FastAPI backend with ML models. This variant offloads the LLM (llama-cpp) to
# an NVIDIA GPU; the embedding / reranker / classifier stay on CPU to spare VRAM
# (the LLM is ~95% of the latency and the 8 GB budget is tight).
#
# Prereq: NVIDIA Container Toolkit in the WSL Docker host — see docker/api/GPU.md.
# Build:  docker compose build api
# Run:    docker compose up -d --force-recreate api   (needs the GPU reservation
#         block in docker-compose.yml on this branch)
# =============================================================================

# CUDA 12.4 *runtime* base (ships libcudart + cuBLAS that the llama-cpp CUDA
# wheel links against). Ubuntu 22.04 = a tag that always exists for 12.4;
# Python 3.12 is provided by uv below, not by apt. Keep this CUDA minor (12.4)
# aligned with the llama-cpp wheel index (cu124).
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

WORKDIR /app

# ── System dependencies ──────────────────────────────────────────────────────
# ca-certificates : let uv fetch its managed CPython + wheels over HTTPS
# libpq-dev       : psycopg build headers
# build-essential : C-extension fallback builds
# curl            : healthcheck
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
        ca-certificates libpq-dev build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# ── Install uv ──────────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# uv provides CPython 3.12 (managed/standalone) regardless of the Ubuntu 22.04
# system Python (3.10) — downloads it on first sync.
ENV UV_PYTHON=3.12

# ── Dependencies (cached layer) ─────────────────────────────────────────────
# 1. Resolve from the (CPU-pinned) pyproject: torch CPU + CPU llama-cpp wheel.
# 2. Swap the CPU llama-cpp wheel for the CUDA 12.4 prebuilt wheel (no nvcc /
#    source build). torch stays CPU on purpose — only the LLM goes to the GPU.
#    Same version pin as pyproject; --no-deps leaves resolved deps untouched.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --group ml-api && \
    uv pip install --force-reinstall --no-deps \
        "llama-cpp-python>=0.3.0,<0.4" \
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

# ── Application code ─────────────────────────────────────────────────────────
COPY src/ src/

# ── Runtime config ───────────────────────────────────────────────────────────
# -1 = offload ALL layers to the GPU. Drop to a partial count (e.g. 24) if the
# 8 GB VRAM OOMs at load — see docker/api/GPU.md for the tuning ladder.
ENV LLM_N_GPU_LAYERS=-1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/root/.cache/huggingface

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=30 --start-period=480s \
    CMD curl -f http://localhost:8000/api/docs || exit 1

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
