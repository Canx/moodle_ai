# Dockerfile for FastAPI backend
FROM python:3.11-slim

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
    libnss3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Create necessary directories first
RUN mkdir -p /app/downloads && \
    mkdir -p /home/appuser/.cache && \
    mkdir -p /home/appuser/.local/bin

WORKDIR /app

# Install Python packages globally first
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Playwright and its dependencies
RUN DEBIAN_FRONTEND=noninteractive playwright install-deps chromium && \
    playwright install chromium

# Now copy the Playwright files and set permissions
RUN mkdir -p /home/appuser/.cache/ms-playwright && \
    cp -r /root/.cache/ms-playwright/* /home/appuser/.cache/ms-playwright/ && \
    chown -R appuser:appuser /app /home/appuser/.cache /home/appuser/.local

# Switch to non-root user
USER appuser

# Set PATH to include user's local bin
ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copy application files
COPY --chown=appuser:appuser . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
