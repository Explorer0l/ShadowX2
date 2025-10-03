# syntax=docker/dockerfile:1.6
# Multi-stage build for optimized production image
FROM python:3.12-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with BuildKit cache for pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip wheel setuptools && \
    pip install -r requirements.txt

# Production stage
FROM python:3.12-slim as production

# Create non-root user for security
RUN groupadd -r shadowx && useradd -r -g shadowx shadowx && \
    mkdir -p /home/shadowx && chown -R shadowx:shadowx /home/shadowx

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRANSFORMERS_NO_TF=1 \
    TRANSFORMERS_NO_FLAX=1 \
    TRANSFORMERS_NO_TORCHVISION=1 \
    HOME=/home/shadowx \
    XDG_CACHE_HOME=/app/cache \
    HF_HOME=/app/cache/hf \
    TORCH_HOME=/app/cache/torch \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=shadowx:shadowx . .

# Create necessary directories with proper permissions
RUN mkdir -p /data /app/logs /app/cache /app/cache/hf /app/cache/torch && \
    chown -R shadowx:shadowx /data /app/logs /app/cache

# Production environment defaults
ENV DB_PATH=/data/bot_database.db \
    AI_PROFANITY_ENABLED=1 \
    AI_BACKEND=ensemble \
    AI_DISABLE_HF=0 \
    AI_PROFANITY_THRESHOLD=0.7 \
    SPAM_SCORE_THRESHOLD=0.6 \
    LOG_LEVEL=INFO \
    PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/data/bot_database.db').close()" || exit 1

# Optional: prefetch AI models at build time
ARG PREFETCH_MODELS=0
RUN if [ "$PREFETCH_MODELS" = "1" ]; then \
        su shadowx -c "XDG_CACHE_HOME=/app/cache HF_HOME=/app/cache/hf TORCH_HOME=/app/cache/torch python -c 'import os; os.environ[\"AI_PROFANITY_ENABLED\"]=\"1\"; from utils.filters import _ensure_ai_loaded; _ensure_ai_loaded(); print(\"Prefetch done\")'" ; \
    fi

# Switch to non-root user
USER shadowx

# Expose port for potential webhooks
# No ports exposed (long polling)

# Run application
CMD ["python", "bot.py"]

