# LinkedIn MCP Server Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV LOG_FORMAT=json

# Expose port for HTTP transport (if used)
EXPOSE 8000

# Run the server
CMD ["uv", "run", "linkedin-mcp"]
