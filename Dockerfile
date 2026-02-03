# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libsqlite3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config/ ./config/
COPY storage/ ./storage/
COPY cli/ ./cli/
COPY api/ ./api/
COPY collectors/ ./collectors/
COPY processing/ ./processing/
COPY main.py ./

# Create necessary directories
RUN mkdir -p data logs config

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PAIS_DATA_DIR=/app/data
ENV PAIS_LOG_DIR=/app/logs
ENV PAIS_CONFIG_DIR=/app/config
ENV PAIS_DB_PATH=/app/data/activity_system.db

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command - run the main scheduler and API server
CMD ["python", "main.py"]
