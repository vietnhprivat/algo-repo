# Dockerfile for algo-repo
# This image is used by Prefect Docker worker to run flows as ephemeral containers.
FROM python:3.13-slim

ARG GIT_SHA=""
ENV GIT_SHA=${GIT_SHA}

# TORCH_VARIANT selects which torch wheel set to install: "cuda" (default, PyPI
# wheels with CUDA 13 NVIDIA libs, ~3 GB) or "cpu" (download.pytorch.org/whl/cpu,
# ~250 MB). CI uses "cpu" to fit the GHA runner's disk budget; prod uses "cuda".
ARG TORCH_VARIANT=cuda

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy lockfile + manifest first so the heavy dep install layer caches on uv.lock alone
# (any src/ change would otherwise bust the layer cache for uv sync).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-workspace --extra ${TORCH_VARIANT}

# Copy project sources and install the workspace packages on top of cached deps.
COPY src/ ./src/
RUN uv sync --frozen --extra ${TORCH_VARIANT}

# Add virtual environment bin to PATH so prefect and all packages are available
ENV PATH="/app/.venv/bin:$PATH"
