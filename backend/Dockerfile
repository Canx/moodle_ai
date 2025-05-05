# Dockerfile for FastAPI backend
FROM python:3.11-slim

# Create non-root user first
RUN useradd -m -u 1000 appuser

# Install required packages for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgconf-2-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libnspr4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browser as root
RUN playwright install chromium && \
    DEBIAN_FRONTEND=noninteractive playwright install-deps chromium

# Create necessary directories and set permissions
RUN mkdir -p /app/downloads && \
    mkdir -p /home/appuser/.cache && \
    chown -R appuser:appuser /app /home/appuser/.cache

# Copy application files
COPY --chown=appuser:appuser . .

# Switch to non-root user after everything is set up
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
