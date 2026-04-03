# Multi-stage build: SvelteKit frontend + Django backend
# Used by Railway for the single production service

# ── Stage 1: Build SvelteKit frontend ──────────────────────────────
FROM node:24-slim AS frontend-build

RUN corepack enable

WORKDIR /frontend

# Install dependencies (cached layer)
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source and build
COPY frontend/ .
RUN pnpm build

# ── Stage 2: Django application ────────────────────────────────────
FROM python:3.14-slim AS base

# Build deps so Pillow compiles from source with AVIF support
# (python:3.14-slim pre-built wheels lack AVIF codec)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    libjpeg62-turbo-dev \
    libfreetype-dev \
    liblcms2-dev \
    libwebp-dev \
    libavif-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (cached layer)
# --no-binary-package pillow forces source build against system libavif
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-binary-package pillow

# Copy application code
COPY backend/ .

# Copy frontend build output from stage 1
COPY --from=frontend-build /frontend/build /app/frontend_build

# Collect static files (Django admin CSS, etc.)
RUN DJANGO_SETTINGS_MODULE=config.settings \
    SECRET_KEY=build-placeholder \
    DEBUG=false \
    uv run python manage.py collectstatic --noinput

EXPOSE 8000

# Shell form so ${PORT:-8000} is expanded; Railway auto-injects PORT
CMD .venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2
