# Dockerfile for algo-repo
# This image is used by Prefect Docker worker to run flows as ephemeral containers.
FROM python:3.13-slim

# Build-time arg: Git SHA baked into image for production tracking
ARG GIT_SHA=""
ENV GIT_SHA=${GIT_SHA}

# Torch variant: "cuda" (default, ~3 GB) or "cpu" (~250 MB)
ARG TORCH_VARIANT=cuda

# Runtime env consumed by observability_wandb (set via Prefect flow env or .env):
#   WANDB_API_KEY    - DTU academic API key
#   WANDB_ENTITY     - team workspace
#   WANDB_PROJECT    - default research project (algo-research)
#   WANDB_MODE       - set to "disabled" to no-op

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# UV_LINK_MODE=copy because the BuildKit cache mount lives on a separate
# filesystem from /app/.venv, so uv's default hardlink mode would fail.
ENV UV_LINK_MODE=copy

# Copy lockfile + manifest first so the heavy dep install layer caches on uv.lock alone
# (any src/ change would otherwise bust the layer cache for uv sync).
# --mount=type=cache persists uv's wheel cache across builds even when the
# layer cache is busted by a uv.lock change — only new/changed wheels download.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --extra ${TORCH_VARIANT}

# Copy project sources and install the workspace packages on top of cached deps.
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra ${TORCH_VARIANT}

# Add virtual environment bin to PATH so prefect and all packages are available
ENV PATH="/app/.venv/bin:$PATH"
