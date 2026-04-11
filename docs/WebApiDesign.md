# Web API Design

This document defines how backend APIs should be designed for the web application, and how the frontend should consume them.

It is not a system-architecture document. It is a development rule for how SvelteKit pages should obtain data from Django.

## Two API types

The backend serves two distinct kinds of endpoints for different purposes:

| API type     | Path             | Purpose                                   |
| ------------ | ---------------- | ----------------------------------------- |
| Resource API | `/api/...`       | Reusable domain data and write operations |
| Page API     | `/api/pages/...` | One route's rendering payload             |

- **Resource APIs** under `/api/...` expose reusable domain data: CRUD operations, autocomplete, lookups, edit forms, and bulk exports.
- **Page APIs** under `/api/pages/...` expose route-shaped payloads optimized for one page. A page endpoint returns a **page model**: exactly the data one specific page needs to render.

## Core Rule

Prefer **page-oriented endpoints** over client-or-server fanout.

For an important page, especially an SSR page, the default should be:

- one route-specific backend endpoint
- one fetch in the page load path
- one response shaped for that page

Do not default to building a page by calling several generic endpoints and stitching them together in Svelte.

## Why

This rule exists for performance, reliability, and code clarity.

### Lower latency

Every extra API call is on the critical path to HTML.

For SSR pages, a route that calls four endpoints is usually slower than a route that calls one page-oriented endpoint that already contains the data the page needs.

### Less orchestration in the frontend

The page should render data, not assemble it.

Hierarchy expansion, related-object selection, sorting rules, fallback logic, and other page composition policy usually belong in Django, not repeated in Svelte route code.

### Better failure behavior

One page endpoint can fail coherently.

Fanout produces partial-failure cases where one call succeeds, another fails, and the frontend has to guess how to degrade.

### Better caching

A page-model response is easier to cache than several smaller calls with page-specific merge logic in the frontend.

## What A Good Page Endpoint Looks Like

A good page-oriented endpoint:

- returns exactly the fields the page needs
- includes already-expanded related data the page needs to render
- applies the page's canonical sort and selection rules
- avoids forcing the route to issue follow-up fetches for obvious related data
- has a stable response shape that maps cleanly to the page UI

The response is a **page model**, not a raw dump of the underlying database model.

## Namespace Convention

Page-oriented endpoints should usually live under a distinct namespace:

- reusable resource endpoints stay under `/api/...`
- page-shaped view-model endpoints should usually live under `/api/pages/...`

Examples:

- `/api/titles/{slug}` for the canonical title resource
- `/api/pages/title/{slug}` for the title detail page model
- `/api/pages/home` for the homepage payload

This is not about following a universal industry standard. It is about keeping two different API types clearly separated:

- resource APIs expose reusable domain data
- page APIs expose route-shaped payloads optimized for one page

Avoid mixing page-specific view models into the general resource namespace unless there is a strong reason.

Page-oriented endpoints should usually also be tagged `tags=["private"]` in Django Ninja so they do not appear in the public API docs. They are internal website endpoints, not part of the public reusable API surface.

## What To Avoid

Avoid this pattern:

1. fetch entity
2. fetch related list
3. fetch taxonomy or lookup data
4. merge and expand in Svelte
5. render

Prefer this pattern:

1. fetch page model
2. render

## Example

For a public SSR page like a title detail page:

Avoid:

1. fetch the title
2. fetch related models
3. fetch related taxonomy or auxiliary lookup data
4. merge and normalize in Svelte
5. render

Prefer:

1. fetch one `title page` endpoint from `+page.server.ts` or `+layout.server.ts`
2. place that endpoint under `/api/pages/...`, for example `/api/pages/title/{slug}`
3. return a response that already contains the title, the related models the page needs, and any display-ready related data
4. render that page model directly

The backend should own the page composition rules. Svelte should render the resulting page model.

## When Generic Endpoints Are Still Appropriate

Generic endpoints are still appropriate when:

- the UI is highly interactive and CSR-only
- the same resource is reused across many unrelated pages
- the route is an internal tool where SSR and crawlability do not matter
- the response is naturally resource-oriented and does not require page-specific composition

Examples:

- autocomplete
- small lookup collections
- edit forms that load one entity for mutation
- reusable internal admin-style tools

## SSR Guidance

For SSR pages, assume the load path is latency-sensitive.

Default to one page endpoint for:

- public detail pages
- public index pages that need SEO
- any route where the initial HTML should contain the meaningful content

Be skeptical of SSR routes that call multiple backend endpoints from `load()`. That should be a deliberate exception, not the default design.

## How Server-Side Routes Should Call Django

Server-side Svelte routes should call Django through `createServerClient` from `$lib/api/server`, not through ad hoc fetch wrappers or direct backend internals.

`createServerClient(fetch, url)` resolves `INTERNAL_API_BASE_URL` (direct-to-Django in production) with a fallback to the request origin (Vite proxy in dev). See `docs/Svelte.md` for the full pattern.

This keeps the boundary clean:

- Django remains the source of truth for data shape
- OpenAPI remains the contract
- generated TypeScript types remain in use
- SvelteKit renders data returned by Django instead of reconstructing it

Do not treat SSR routes as a place to bypass the backend contract. The page may render on the server, but it should still consume Django through the API boundary.

## Frontend / Backend Contract

The backend API remains the source of truth for the contract.

- Django Ninja defines the schema
- OpenAPI is generated from Django
- TypeScript types are generated from OpenAPI

The goal is not "thin backend, smart page assembly." The goal is a clean contract where the backend exports the data shape the page actually needs.

## Heuristic

When building a page, ask:

"If I removed all frontend data-merging code, what single backend response would I wish I already had?"

That response shape is usually the endpoint you should build.
