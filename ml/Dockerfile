FROM python:3.11-slim

WORKDIR /app

# System deps for rasterio/GDAL (required by rioxarray)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Compose builds from the repository root so the shared contract is available.
COPY ml/pyproject.toml ml/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Copy application code and cache
COPY ml/app/ ./app/
COPY ml/cache/ ./cache/
COPY shared/ ./shared/

EXPOSE 8001
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
