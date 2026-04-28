# Django App Boundaries

This document defines the dependency rules and responsibilities of Pinbase's Django apps.

## Apps

- `core`: shared foundation layer used by the rest of the project
- `accounts`: authentication and account-specific behavior
- `catalog`: the pinball business/domain/data model
- `citation`: citation-source metadata and evidence objects that can be cited
- `provenance`: claims, source, and audit system
- `media`: media upload and hosting infrastructure

## Dependencies

```text
           media.api
           catalog
____________________________
provenance | media.{models,storage,processing,schemas} | citation
____________________________
      core | accounts
```

- `core` and `accounts` depend on nothing
- `citation`, `provenance`, and `media.{storage,processing,schemas}` are peer-isolated (must not depend on each other). `media.models` is permitted one targeted dependency on `provenance.models` for `ClaimControlledModel` only — `media_attachment` is a claim field, so any `MediaSupportedModel` entity is by construction a `ClaimControlledModel`; the inheritance encodes that structural commitment as a compile-time guarantee. The rest of `media.models` (concrete `MediaAsset` / `MediaRendition` / `EntityMedia`) does not reach into provenance.
- `provenance` depends on `citation` but `citation` does not depend on `provenance`
- `catalog` uses the full middle tier
- `media.api` depends on `catalog` and `provenance`: upload handlers write `media_attachment` claims through catalog's relationship-claim registry and persist `Claim` rows directly. This is a structural consequence of `media_attachment` being a catalog-registered relationship type whose target happens to live in media; splitting it out would require extracting the whole relationship-claim machinery into a neutral app

## Exception: Page API endpoints

Page API endpoints (see [ApiDesign.md § Two API types](ApiDesign.md#two-api-types)) are expected to cross app layers. A page endpoint's job is to return one route's full rendering payload, which routinely means reading from several apps and returning a composed page model.

A page endpoint lives in the app that owns the _page concept_, not the app that owns the most data it reads. The title detail page is about a title, so `/api/pages/title/{slug}` lives in catalog even though it reads claims from provenance and attachments from media. The user profile page is about a user, so `/api/pages/user/{username}/` lives in accounts even though it reads ChangeSets and Claims from provenance.

The rules above apply to the non-page surface (models, services, helpers). Page endpoints are an intentional carve-out and should not be refactored to obey peer isolation at the cost of the page-composition pattern.
