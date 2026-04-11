# Architecture

This documents the project's system architecture.

## High-Level Shape

Pinbase is a Django + SvelteKit monorepo with a small number of clear subsystems.

- Django owns the backend: data model, provenance/claims logic, ingest pipeline, API, and admin UI.
- SvelteKit owns the frontend.
- The production system is deployed as a single service.
- The single production service includes both Django and a SvelteKit Node SSR runtime behind one reverse proxy.

At a high level:

```text
Browser
  -> same-origin web application
     -> Django API and admin
     -> SvelteKit frontend rendered via Node SSR
```

## Major Pieces

### Web application

The web application is split between Django and SvelteKit.

- Django owns the backend, API, admin, auth authority, and business truth.
- SvelteKit owns the user-facing frontend.

See [WebArchitecture.md](WebArchitecture.md) for request flow, same-origin behavior, and the SSR/CSR split.

### Backend application layers

Within Django, responsibilities are split across a few explicit backend apps:

- `core` shared foundation layer.
- `accounts` auth/account-specific behavior.
- `catalog` the pinball business/domain model.
- `citation` citation-source metadata and evidence records.
- `provenance` the claims and audit machinery.
- `media` photo and video upload and hosting infrastructure.

See [AppBoundaries.md](AppBoundaries.md) for dependency rules and boundary guidance.

## Read Next

- [Overview.md](Overview.md)
- [WebArchitecture.md](WebArchitecture.md)
- [Hosting.md](Hosting.md)
- [DomainModel.md](DomainModel.md)
- [AppBoundaries.md](AppBoundaries.md)
- [Provenance.md](Provenance.md)
- [Ingest.md](Ingest.md)
