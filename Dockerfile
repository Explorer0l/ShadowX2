FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for aiohttp SSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (CPU-only, without Detoxify to avoid conflicts/size)
RUN pip install --upgrade pip wheel setuptools
RUN pip install aiogram==3.15.0 aiohttp==3.9.5 python-dotenv==1.0.1 langid==1.1.6
# CPU torch only
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.1
# Detoxify requires transformers==4.22.1
RUN pip install transformers==4.22.1 huggingface-hub==0.24.6 detoxify==0.5.1

# Copy project
COPY . .

# Create data dir for SQLite if DB_PATH not set (mounted volume recommended)
RUN mkdir -p /data

# Default envs (override in compose or runtime)
ENV DB_PATH=/data/bot_database.db \
    AI_PROFANITY_ENABLED=1 \
    AI_BACKEND=ensemble \
    AI_DISABLE_HF=0 \
    AI_PROFANITY_THRESHOLD=0.7 \
    SPAM_SCORE_THRESHOLD=0.6

# Optional: prefetch HF model at build time to avoid first-run download (set --build-arg PREFETCH_MODELS=1)
ARG PREFETCH_MODELS=0
RUN if [ "$PREFETCH_MODELS" = "1" ]; then \
      python - << 'PY'\
from transformers import AutoTokenizer, AutoModelForSequenceClassification\
from detoxify import Detoxify\
m='cointegrated/rubert-tiny-toxicity'\
AutoTokenizer.from_pretrained(m); AutoModelForSequenceClassification.from_pretrained(m)\
Detoxify('multilingual')\
print('HF and Detoxify models cached')\
PY
    ; fi

# Run
CMD ["python", "bot.py"]

