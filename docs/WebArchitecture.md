# Web Architecture

This document describes how Pinbase's web application behaves at runtime: how browser requests flow through the stack, how same-origin is preserved, and how SSR and CSR are split between routes.

For the top-level system map, see [Architecture.md](Architecture.md). For deployment and operator details, see [Hosting.md](Hosting.md).

## Web Split

### Django backend

Django is the source of truth for:

- the catalog and supporting models
- provenance, claim assertion, and claim resolution
- ingest from external and editorial sources
- authentication and authorization
- admin and operational tooling
- the API exported to the frontend

### SvelteKit frontend

SvelteKit is responsible for:

- the public-facing browsing experience
- authenticated user-facing application flows
- consuming the Django API
- rendering server-side HTML for public pages
- rendering CSR-only application pages where interactivity or auth-gated UX is the priority

The frontend does not own business truth. It renders and edits data through Django.

## Same-Origin Model

Pinbase uses a same-origin model in both development and production.

### Why

This keeps authentication and CSRF simple:

- Django session auth works naturally
- the browser does not need cross-origin API calls
- no JWT or CORS architecture is required
- Django admin and the user-facing app share the same auth authority

## Development

In local development, the browser talks to the SvelteKit dev server. Vite handles frontend routes and proxies backend paths to Django.

```text
Browser
  -> SvelteKit dev server
     -> /api/*, /admin/*, /media/*, /static/* proxied to Django
     -> frontend routes handled by SvelteKit
```

Public routes can still be server-rendered in development because SvelteKit's dev server supports SSR directly. This preserves the same-origin mental model even though two processes are running.

## Production

In production, one Railway service handles:

- `/api/` via Django Ninja
- `/admin/` via Django admin
- `/media/` via Django storage/media handling
- `/static/` via Django/WhiteNoise
- frontend routes via SvelteKit Node SSR

At a high level:

```text
Browser
  -> Caddy
     -> /api/* handled by Django/Gunicorn
     -> /admin/* handled by Django admin
     -> /media/* handled by Django/media storage
     -> /static/* handled by Django/WhiteNoise
     -> frontend routes handled by SvelteKit Node SSR
```

See [Hosting.md](Hosting.md) for the production serving details.

## Rendering Model

Pinbase uses both SSR and CSR, but not for the same kinds of routes.

- Public content-heavy routes should usually render meaningful HTML on the server.
- Internal or highly interactive application routes may deliberately opt out with `ssr = false`.
- The decision is per route, not all-or-nothing for the whole frontend.

See [Svelte.md](Svelte.md) for route-level guidance and [WebApiDesign.md](WebApiDesign.md) for page-oriented API design.

## Read Next

- [Architecture.md](Architecture.md)
- [Svelte.md](Svelte.md)
- [WebApiDesign.md](WebApiDesign.md)
- [Hosting.md](Hosting.md)
