FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv

WORKDIR /app

# Copy dependency file first for better layer caching
COPY pyproject.toml .

# Install dependencies (without dev extras for production layer)
# Using --system to install into the global Python environment inside the container
RUN uv pip install --system -e "."

# Copy application source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
