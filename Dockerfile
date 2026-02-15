# Dockerfile for algo-repo
# This image is used by Prefect Docker worker to run flows as ephemeral containers.
FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files (no .env — secrets are passed via environment variables)
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install all workspace dependencies
RUN uv sync --frozen

# Add virtual environment bin to PATH so prefect and all packages are available
ENV PATH="/app/.venv/bin:$PATH"
