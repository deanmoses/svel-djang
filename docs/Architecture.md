# Architecture

This documents the project's system architecture.

## High-Level Shape

This is a Django + SvelteKit monorepo with a small number of clear subsystems.

- Django owns the backend: data model, provenance/claims logic, ingest pipeline, API, and admin UI.
- SvelteKit owns the frontend.
- The production system is deployed as a single service.
- No Node.js server runs in production.

At a high level:

```text
Browser
  -> same-origin web application
     -> Django API and admin
     -> built SvelteKit frontend
```

## Major Pieces

### Web application

The web application is split between Django and SvelteKit.

- Django owns the backend, API, admin, auth authority, and business truth.
- SvelteKit owns the user-facing frontend.
- The browser interacts with the system through a same-origin model in both development and production.

See [WebArchitecture.md](WebArchitecture.md).

### Backend application layers

Within Django, responsibilities are split across backend apps with explicit boundaries.

- `core` shared foundation layer.
- `catalog` the pinball business/domain model.
- `provenance` the claims and audit machinery.
- `media` photo and video upload and hosting infrastructure.
- `accounts` auth/account-specific behavior.

These boundaries matter because Pinbase's value depends on a clear domain model, a generic provenance engine, and infrastructure concerns that do not leak across the system.

See [AppBoundaries.md](AppBoundaries.md).

## Read Next

- [Overview.md](Overview.md)
- [DomainModel.md](DomainModel.md)
- [WebArchitecture.md](WebArchitecture.md)
- [AppBoundaries.md](AppBoundaries.md)
- [Provenance.md](Provenance.md)
- [Ingest.md](Ingest.md)
- [Hosting.md](Hosting.md)
