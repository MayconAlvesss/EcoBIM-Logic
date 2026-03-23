FROM python:3.11-slim-bookworm

LABEL maintainer="Aura Ecosystem"
# TODO: move to multi-stage build to reduce image size. this is too fat right now.

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# had to add build-essential for some pip packages to compile correctly
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# running as root is bad, setting up a dummy user
RUN useradd -m auraserver
USER auraserver

EXPOSE 8000

# FIXME: hardcoded workers=1. need to pass this dynamically via env var in prod
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]