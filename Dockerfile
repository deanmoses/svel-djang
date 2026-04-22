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
# Keep only runtime dependencies for the Node SSR server we copy below.
RUN pnpm prune --prod

# ── Stage 2: Runtime dependencies for Caddy + Node ────────────────
FROM node:24-slim AS node-runtime

FROM caddy:2.11.2 AS caddy-runtime

# ── Stage 3: Django + SSR application ──────────────────────────────
FROM python:3.14-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=caddy-runtime /usr/bin/caddy /usr/local/bin/caddy

WORKDIR /app
ENV INTERNAL_API_BASE_URL=http://127.0.0.1:8000

# Install dependencies (cached layer)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY backend/ .

# Copy frontend runtime artifacts from stage 1
COPY --from=frontend-build /frontend/build /app/frontend_runtime/build
COPY --from=frontend-build /frontend/node_modules /app/frontend_runtime/node_modules
COPY --from=frontend-build /frontend/package.json /app/frontend_runtime/package.json

# Reverse-proxy and startup config
COPY Caddyfile /app/Caddyfile
COPY scripts/start-production /app/scripts/start-production
RUN chmod +x /app/scripts/start-production

# Collect static files (Django admin CSS, etc.)
RUN DJANGO_SETTINGS_MODULE=config.settings \
    SECRET_KEY=build-placeholder \
    DEBUG=false \
    uv run python manage.py collectstatic --noinput

EXPOSE 8080

CMD ["/app/scripts/start-production"]
