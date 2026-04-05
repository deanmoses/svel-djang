# Svelte

This document defines how to think about SvelteKit pages in Pinbase.

It is not about Svelte syntax or component style. It is about route behavior: which pages should render on the server, which should stay client-only, and how routes should obtain data from Django.

## Default Model

Use SvelteKit as the page runtime and Django as the data authority.

- Django owns the data model, business logic, auth, and API contract.
- SvelteKit owns page rendering and user-facing UI composition.
- Public pages should usually render meaningful HTML on the server.
- Internal or heavily interactive application pages may stay client-rendered.

## Public SSR Pages

Default to SSR for pages where the initial HTML matters.

This usually means:

- public detail pages
- public browse/index pages that should be crawlable
- pages where content should appear in the first response without waiting for client fetches

For these routes, prefer:

- `+page.server.ts` for route data loading
- one page-oriented backend endpoint
- `+page.svelte` that renders the returned data directly

The page should receive a page model and render it. It should not orchestrate multiple backend calls unless there is a strong reason.

## CSR-Only Pages

Use `ssr = false` deliberately, not by default.

This is appropriate for:

- authenticated app surfaces
- pages dominated by in-browser state and interaction
- internal tools where SEO and first-response HTML are not important
- routes where the browser-only environment is central to the experience

Examples in this repo include authenticated application layouts that intentionally opt out of SSR.

## Choosing Between SSR And CSR

Ask:

1. Does the first HTML response need to contain the actual content?
2. Is this page public and important for discovery or sharing?
3. Is the page mostly presentation of backend data, or mostly client interaction?

If the page is public and content-heavy, prefer SSR.

If the page is internal, highly interactive, or intentionally app-like, CSR is often the better fit.

## Route Files

Use route files by responsibility:

- `+page.server.ts` for server-side page loading
- `+layout.server.ts` for shared server-side loading across a route subtree
- `+page.ts` only when the route logic truly needs universal load behavior
- `+page.svelte` and `+layout.svelte` for rendering

For public SSR pages, `+page.server.ts` or `+layout.server.ts` should be the default choice.

## Calling Django From Server-Side Routes

Server-side Svelte routes should call Django APIs through the typed client, not through ad hoc fetch helpers.

Pattern:

- if `INTERNAL_API_BASE_URL` is set, use `createApiClient(fetch, INTERNAL_API_BASE_URL)`
- otherwise, use the current request origin as the base URL, for example `createApiClient(fetch, url.origin)`
- in local development, this keeps SSR on the same Vite-proxied path the browser uses
- in production, `INTERNAL_API_BASE_URL` should point at Django's internal address, currently `http://127.0.0.1:8000`
- call one backend endpoint that already matches the page's needs

This keeps:

- OpenAPI-generated types in use
- request logic consistent between routes
- backend/frontend contracts explicit

The goal is not for SvelteKit SSR to reach into Django internals. The boundary stays at the HTTP API.

## What To Avoid

Avoid these patterns on SSR pages:

- calling several generic endpoints from one route and merging them in Svelte
- moving backend composition logic into `load()`
- using browser-only fetch patterns for data that belongs in the initial HTML
- marking routes `ssr = false` just because client fetching is familiar

## Heuristic

When building a page, ask:

"Should this page arrive as content, or as an app shell that later discovers its content?"

If it should arrive as content, prefer SSR.
