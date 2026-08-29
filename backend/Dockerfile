# Production Backend Dockerfile — Chargeback Shield Task 8.2
# Minimal, isolated, non-root Python 3.11 container

FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build & processing dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Final Runtime Stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root system user & group
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# Create persistent storage directories & set ownership
RUN mkdir -p /app/storage/evidence /app/storage/processed /app/data && \
    chown -R appuser:appgroup /app

# Copy application source code (ignoring .env via .dockerignore)
COPY --chown=appuser:appgroup backend /app/backend

# Switch to non-root user
USER appuser

# Expose internal backend port (Not exposed publicly directly)
EXPOSE 8000

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8000

# Health check targeting local health endpoint without Razorpay calls
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Production ASGI server command
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
