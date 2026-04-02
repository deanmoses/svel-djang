# Web Architecture

This document describes how Pinbase's web application is split between Django and SvelteKit, how browser requests flow through the stack, and why the system uses a same-origin model.

For the top-level system map, see [Architecture.md](Architecture.md). For deployment details, see [Hosting.md](Hosting.md).

## Responsibilities

### Django backend

Django is the source of truth for:

- the catalog and supporting models
- provenance, claim assertion, and claim resolution
- ingest from external and editorial sources
- authentication and authorization
- admin and operational tooling
- the API contract exported to the frontend

### SvelteKit frontend

SvelteKit is responsible for:

- the public-facing browsing experience
- authenticated user-facing application flows
- consuming the Django API
- rendering prerendered public pages and CSR application pages

The frontend does not own business truth. It presents and edits data through the backend.

## Same-Origin Model

Pinbase uses a same-origin model in both development and production.

### Why

This keeps authentication and CSRF simple:

- Django session auth works naturally
- the browser does not need cross-origin API calls
- no JWT or CORS architecture is required
- Django admin and the user-facing app share the same auth authority

## Development

In local development, the browser talks to the SvelteKit dev server, which proxies `/api/` and `/admin/` to Django.

```text
Browser
  -> SvelteKit dev server
     -> /api/*, /admin/* proxied to Django
     -> frontend routes handled by SvelteKit
```

This preserves the same-origin mental model during development even though two processes are running.

## Production

In production, one Django service handles:

- `/api/` via Django Ninja
- `/admin/` via Django admin
- static frontend assets
- prerendered HTML or the SPA shell for frontend routes

At a high level:

```text
Browser
  -> Django/Gunicorn
     -> /api/* handled by Django Ninja
     -> /admin/* handled by Django admin
     -> static assets served from the built frontend output
     -> frontend routes served as prerendered HTML or SPA shell
```

See [Hosting.md](Hosting.md) for the production serving details.

## API Contract

The backend API is the contract between Django and the frontend.

- Django Ninja exposes the API schema.
- TypeScript types are generated from the OpenAPI output.
- The generated types are derived artifacts, not the source of truth.

This keeps the frontend strongly typed without making TypeScript definitions a separate hand-maintained interface.

## Runtime Model

Pinbase intentionally avoids a separate frontend runtime in production.

- Node.js is used during frontend development and build time.
- Node.js does not run in production to serve the site.
- Django remains the single production runtime for API, admin, and frontend delivery.

This keeps the deployed system simpler to operate and keeps auth and request handling centered in one place.

## Read Next

- [Architecture.md](Architecture.md)
- [AppBoundaries.md](AppBoundaries.md)
- [Hosting.md](Hosting.md)
