FROM python:3.11-slim

WORKDIR /app

# System deps for rasterio/GDAL (required by rioxarray)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency manifest and install
COPY pyproject.toml .
RUN uv sync --no-dev

# Copy application code and cache
COPY app/ ./app/
COPY cache/ ./cache/

EXPOSE 8001
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8001"]
