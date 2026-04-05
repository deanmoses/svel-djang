# Deployment on Railway

Pinbase runs as a **single [Railway](https://railway.com/) service**: one Docker container running Caddy, SvelteKit Node SSR, and Django/Gunicorn.

This document is the operator-facing reference for production deployment, runtime processes, ports, and troubleshooting.

For browser request flow and the SSR/CSR split, see [WebArchitecture.md](WebArchitecture.md).

## Runtime Topology

```text
Browser ──→ Railway (single Caddy service)
              │
              ├─ frontend routes        → SvelteKit Node SSR
              ├─ /_app/*                → SvelteKit Node SSR
              ├─ /api/*                 → Django Ninja API
              ├─ /admin/*               → Django Admin
              ├─ /media/*               → Django/media storage
              └─ /static/*              → Django staticfiles / WhiteNoise
```

### Runtime flow

1. **Docker multi-stage build**: Stage 1 installs frontend dependencies and
   builds the SvelteKit Node server. The final image contains the built
   Svelte runtime, Django, and Caddy in one container.

2. **Caddy reverse proxy**: Caddy listens on Railway's public `PORT` and
   routes `/api/`, `/admin/`, `/media/`, and `/static/` to Django on
   `127.0.0.1:8000`. All other requests are forwarded to SvelteKit SSR on
   `127.0.0.1:3000`.

3. **WhiteNoise static files**: Django still serves collected static files
   for admin assets through `/static/`. Uploaded media continues to flow
   through Django storage settings.

4. **Migrations on deploy**: Railway's `preDeployCommand` runs
   `manage.py migrate` before the new container accepts traffic. If the
   migration fails, the old container keeps serving.

## Process Model

The production container runs three long-lived processes:

- **Caddy** on Railway's public `PORT`
- **Django/Gunicorn** on `127.0.0.1:8000`
- **SvelteKit Node SSR** on `127.0.0.1:3000`

The entrypoint is [`scripts/start-production`](../scripts/start-production).
It starts all three processes and keeps the container alive while they are all healthy.

### Current supervision behavior

The supervision model is intentionally simple for now:

- there is no in-container restart policy for Node or Gunicorn
- if one of the child processes exits, the container exits shortly after
- Railway is responsible for restarting the container

This is acceptable for the current bootstrap phase because it is simple and fails closed, but it is not a full process supervisor. If the container needs stronger production hardening later, a dedicated supervision layer such as `s6-overlay` would be the next step.

### Route handling examples

| Request                        | Handled by                           |
| ------------------------------ | ------------------------------------ |
| `GET /api/models/`             | Django Ninja                         |
| `GET /admin/`                  | Django Admin                         |
| `GET /__health`                | Caddy → SvelteKit readiness endpoint |
| `GET /titles/medieval-madness` | Caddy → SvelteKit SSR                |
| `GET /_app/immutable/app.js`   | Caddy → SvelteKit SSR                |
| `GET /manufacturers/williams`  | Caddy → SvelteKit SSR                |
| `GET /`                        | Caddy → SvelteKit SSR                |

## Setup

### 1. Create Railway project

In your Railway workspace, create a new project and connect the GitHub repo.
Railway auto-detects the `Dockerfile` via `railway.toml`.

Add a **Postgres** plugin to the project. Railway sets `DATABASE_URL`
automatically via a reference variable.

### 2. Set environment variables

In the Railway service dashboard:

| Variable                | Value                                                                         |
| ----------------------- | ----------------------------------------------------------------------------- |
| `SECRET_KEY`            | Random string: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG`                 | `false`                                                                       |
| `ALLOWED_HOSTS`         | Your Railway domain, e.g. `pinbase-production.up.railway.app`                 |
| `CSRF_TRUSTED_ORIGINS`  | Full origin, e.g. `https://pinbase-production.up.railway.app`                 |
| `INTERNAL_API_BASE_URL` | `http://127.0.0.1:8000`                                                       |

`DATABASE_URL` and `PORT` are set automatically by Railway.

### Runtime environment notes

- `PORT` is the public port Railway assigns to the container. Caddy listens on this port.
- `INTERNAL_API_BASE_URL` is the base URL SvelteKit SSR uses to call Django from server-side routes. In the current production topology it should point directly at Gunicorn on `http://127.0.0.1:8000` so SSR does not bounce back through the public Caddy origin.
- The Docker image sets `INTERNAL_API_BASE_URL=http://127.0.0.1:8000` by default. You should keep that value unless the internal Django address changes.

### 3. Deploy

Push to `main`. Railway builds the Docker image and deploys. The
`preDeployCommand` in `railway.toml` runs migrations before the new
container starts accepting traffic.

### 4. Create superuser (one-time)

In the Railway service shell (or via `railway run`):

```bash
uv run python manage.py createsuperuser
```

## Custom domain

1. Add a custom domain in Railway project settings
2. Update `ALLOWED_HOSTS` to include the domain
3. Update `CSRF_TRUSTED_ORIGINS` to include `https://yourdomain.com`

## Troubleshooting

**Health check fails after deploy**:
The health check should hit `/__health`. That endpoint is served by the
SvelteKit Node runtime and, in turn, checks Django via its internal
`/api/health/` call. If it fails, check the deploy logs for Node or Python
startup errors. Common causes: missing `SECRET_KEY`, database connection
issues, a bad migration, or the SSR process failing to start.

**"Frontend build directory not found" error**:
The Docker build's Node stage failed to produce the SvelteKit SSR runtime.
Check the build logs for pnpm/SvelteKit errors, and confirm the final image
contains the built Node output under `/app/frontend_runtime/`.

**Frontend routes 502 or blank pages**:
Caddy may be up while the SvelteKit Node server failed to start or crashed.
Check the container logs for Node startup errors and confirm the SSR process
is listening on `127.0.0.1:3000`.

**Bad migration**:
`preDeployCommand` runs migrations before swapping containers. If a
migration fails, the old container keeps serving and the deploy is marked
as failed. Fix the migration and push again. Railway does not automatically
roll back the database — if a migration partially applied, you may need to
manually fix it via `railway run`.
