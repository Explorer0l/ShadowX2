FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for aiogram/aiohttp, optional certs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . .

# Create data dir for SQLite if DB_PATH not set (mounted volume recommended)
RUN mkdir -p /data

# Default envs (override in compose or runtime)
ENV DB_PATH=/data/bot_database.db

# Run
CMD ["python", "bot.py"]

