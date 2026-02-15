# Dockerfile for algo-repo
FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY .env ./

# Install all workspace dependencies
RUN uv sync --frozen

# Add virtual environment bin to PATH so prefect command is available
ENV PATH="/app/.venv/bin:$PATH"

# Set Python path so modules can import each other
ENV PYTHONPATH=/app

# Default command - run ingestion flow
CMD ["python", "-m", "schedules.ingestion"]
