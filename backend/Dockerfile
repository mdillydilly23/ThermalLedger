FROM python:3.11-slim

WORKDIR /app

# curl is used by the Compose healthcheck; uv installs the project dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# The Compose build context is the repository root so the service can import
# the shared contract and the worker can run the bootstrap scripts.
COPY backend/pyproject.toml ./pyproject.toml
RUN uv sync --no-dev --no-install-project

# Copy application code, shared contract, and worker scripts.
COPY backend/app/ ./app/
COPY shared/ ./shared/
COPY scripts/ ./scripts/

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
