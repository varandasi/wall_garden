# syntax=docker/dockerfile:1
# Pi-flavoured daemon image. Picamera2 ships via apt on Bookworm so we use
# python:3.11-slim-bookworm + apt rather than the slim `python:slim` image.

FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
      build-essential \
      libi2c-dev \
      python3-libgpiod \
      python3-picamera2 \
      curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager).
COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /uvx /usr/local/bin/

COPY pyproject.toml ./
COPY requirements-pi.txt ./
COPY wallgardend ./wallgardend
COPY config ./config

# Sync core deps and Pi extras. uv lock isn't committed because the Pi
# resolves a different platform than dev macs.
RUN uv pip install --system --no-cache-dir -e . && \
    uv pip install --system --no-cache-dir -r requirements-pi.txt

# wallgarden user must be in the i2c, gpio, video groups (compose handles this
# via group-add in the Kamal accessory config).
RUN groupadd -r wallgarden && useradd -r -g wallgarden -d /app wallgarden && \
    chown -R wallgarden:wallgarden /app

USER wallgarden

ENV WALLGARDEN_BACKEND=pi

ENTRYPOINT ["python", "-m", "wallgardend.main"]
