# Documentation Refresh Plan

This document proposes a refreshed documentation set for the project and maps the current docs into it.

## Goals

- Create a real first-stop human document for understanding the product and system.
- Separate product, architecture, domain, and implementation-reference concerns.
- Move implemented architecture out of plan docs and into stable reference docs.
- Reduce overlap between the domain/terminology docs.

## Proposed Documentation Set

### Contributor entrypoint

- [README.md](../../README.md)
  Keep this as contributor quickstart only: setup, commands, local dev, CI expectations. It should not try to carry the product or system narrative.

### Product docs

- `docs/Overview.md`
  New. This should be the first-stop human document. It should explain what Pinbase is, who it serves, the main product surfaces, where data comes from, and the high-level shape of the system.

- [docs/DomainModel.md](../DomainModel.md)
  Keep, but narrow and strengthen it. This doc should describe the business domain of pinball as Pinbase understands it: Titles, Models, variants, remakes, manufacturers, taxonomy, locations, credits, and related concepts. This is not a technical entity-model or schema-reference doc. It is the product-facing domain model: how the public thinks about pinball, how the museum thinks about pinball, and how Pinbase organizes the world so information can slot in cleanly. It should open with a short "Terminology" or "Core distinctions" section that absorbs the most important content from [Definitions.md](../Definitions.md), then proceed into the domain concepts and their relationships. It should stop being part business-domain doc and part ingest design.

## Architecture & system docs

- `docs/Architecture.md`
  New. This should be the short top-level system map: the major pieces of Pinbase, how they relate, and where to go for deeper architectural docs.

- `docs/WebArchitecture.md`
  New. This should describe the Django + SvelteKit web stack: same-origin auth, dev proxy, production serving model, and the API contract between backend and frontend.

- `docs/AppBoundaries.md`
  New. This should document backend app responsibilities and dependency rules, especially the rule that `core` is the shared foundation layer and that `catalog`, `provenance`, and `media` do not depend on one another.

- [docs/Provenance.md](../Provenance.md)
  Rewrite as the canonical reference for claims, resolution, relationship namespaces, `ChangeSet`, `IngestRun`, retractions, and claim-controlled entity lifecycle/status. The now-implemented parts of [ClaimsNextGen.md](ClaimsNextGen.md) and [ChangeSet.md](ChangeSet.md) should move here.

- [docs/Ingest.md](../Ingest.md)
  Rewrite around the current plan/apply architecture, source adapters, dry-run behavior, run reporting, current command surface, and source-specific notes. Operational instructions should remain, but they should be secondary to "how ingest works now".

- `docs/Media.md`
  New stable reference doc. This should describe the media domain, ownership boundary, uploaded-vs-third-party policy, the `MediaAsset` / `MediaRendition` / `EntityMedia` split, and the current implementation status. Source material exists in [Media.md](Media.md).

### Development docs

- `docs/Development.md`
  New. This should be the engineering/navigation doc for contributors working in the codebase. It should point to the more specific development references instead of trying to replace them. In particular, it should link to [DataModeling.md](../DataModeling.md) and a future `docs/Testing.md`.

- `docs/DataModel.md` (only if needed)
  Optional. Create this only if the project ends up needing a lower-level technical reference for the actual Django/entity model, persistence structure, or implementation details that do not belong in [DomainModel.md](../DomainModel.md). Do not let this displace or dilute the importance of the business-domain doc.

- [docs/DataModeling.md](../DataModeling.md)
  Keep as the engineering rules doc for schema design, constraints, and modeling patterns.

- `docs/Testing.md`
  New. This should collect testing strategy and repo-specific testing expectations in one place: how to choose the smallest meaningful test set, TDD expectations for bug fixes, backend/frontend test layout, and any common patterns worth standardizing.

### Operations docs

- [docs/Hosting.md](../Hosting.md)
  Keep as deployment and operations documentation.

## Resulting Reading Order

Suggested human reading order:

1. `docs/Overview.md`
2. `docs/Architecture.md`
3. [DomainModel.md](../DomainModel.md)
4. `docs/WebArchitecture.md`
5. `docs/AppBoundaries.md`
6. [Provenance.md](../Provenance.md)
7. [Ingest.md](../Ingest.md)
8. `docs/Media.md`
9. `docs/Development.md`

Suggested contributor/supporting references:

- [README.md](../../README.md)
- `docs/Development.md`
- `docs/DataModel.md` (if created)
- [DataModeling.md](../DataModeling.md)
- `docs/Testing.md`
- [Hosting.md](../Hosting.md)

## Migration Notes

### Product and architecture split

The biggest missing piece is a genuine overview doc. [README.md](../../README.md) is intentionally lightweight and contributor-oriented. [ProjectBrief.md](ProjectBrief.md) captures early architecture rationale, but not the product. The refresh should therefore create `docs/Overview.md` mostly from scratch, while using [ProjectBrief.md](ProjectBrief.md) only as source material for the architecture docs.

### Domain and terminology split

[DomainModel.md](../DomainModel.md) and [Definitions.md](../Definitions.md) currently overlap too heavily to justify separate docs. The refresh should merge them by:

- Keeping [DomainModel.md](../DomainModel.md) as the canonical business-domain doc
- Adding a short opening "Terminology" or "Core distinctions" section there
- Moving the useful conceptual distinctions from [Definitions.md](../Definitions.md) into that opening section
- Retiring [Definitions.md](../Definitions.md) once its useful content has been absorbed

This keeps one authoritative explanation of `Title`, `Model`, `Variant`, `Remake`, and related distinctions in the product's core domain language.

If the project later needs a lower-level technical reference for the actual Django/entity model, that should live in a separate `docs/DataModel.md`, not in [DomainModel.md](../DomainModel.md).

### Development docs split

The repo also needs an explicit development-doc entrypoint. Today contributor guidance is spread across [README.md](../../README.md), [DataModeling.md](../DataModeling.md), [AGENTS.src.md](../AGENTS.src.md), and inline conventions. A new `docs/Development.md` should gather and route that information:

- `docs/Development.md` as the contributor-facing hub
- [DataModeling.md](../DataModeling.md) for schema/modeling rules
- `docs/Testing.md` for testing strategy and expectations

This keeps the overview and architecture docs from turning into contributor handbooks, while also keeping README from having to carry every engineering convention.

### README refresh

[README.md](../../README.md) is still broadly accurate as a contributor quickstart, but it is too thin and slightly stale as a repository landing page.

What should stay:

- Setup and local development commands
- Core architecture bullets
- Project structure at a high level

What should change:

- Update the description of `docs/` in the project structure section. It is no longer just agent-doc source.
- Add command references for `make pull-ingest` and `make ingest`.
- Add a short "Further reading" section linking to `docs/Overview.md`, `docs/Architecture.md`, `docs/WebArchitecture.md`, `docs/AppBoundaries.md`, [DomainModel.md](../DomainModel.md), [Provenance.md](../Provenance.md), [Ingest.md](../Ingest.md), `docs/Development.md`, and [Hosting.md](../Hosting.md). When a stable media reference exists, include that too.
- Keep README focused on onboarding and navigation, not on carrying the full product/system explanation. That belongs in `docs/Overview.md` and `docs/Architecture.md`.

### Plan docs are historical reference

The `docs/plans/` folder is for historical plans. Those docs are expected to go stale once implementation lands. They should remain available for historical reference, but they are not canonical product or system documentation.

The refresh should move implemented decisions into stable docs such as [Provenance.md](../Provenance.md), [Ingest.md](../Ingest.md), and `docs/Media.md`, while leaving plan docs like [ClaimsNextGen.md](ClaimsNextGen.md), [ChangeSet.md](ChangeSet.md), [Media.md](Media.md), and [ProjectBrief.md](ProjectBrief.md) in place as historical artifacts. A short `docs/plans/README.md` should make that status explicit.

## Proposed End State

After the refresh, the docs should answer these questions cleanly:

- "What is Pinbase?" -> `docs/Overview.md`
- "How is the system put together?" -> `docs/Architecture.md`
- "How is the Django + SvelteKit web app structured?" -> `docs/WebArchitecture.md`
- "What are the backend app dependency rules?" -> `docs/AppBoundaries.md`
- "What is Pinbase's business/domain model of pinball?" -> [DomainModel.md](../DomainModel.md)
- "What do `Title`, `Model`, `Variant`, and related terms mean?" -> [DomainModel.md](../DomainModel.md)
- "How do provenance and claims work?" -> [Provenance.md](../Provenance.md)
- "How does ingest work?" -> [Ingest.md](../Ingest.md)
- "How does media work?" -> `docs/Media.md`
- "How do I work on this codebase?" -> `docs/Development.md`
- "What is the lower-level technical/entity model?" -> `docs/DataModel.md` (if needed)
- "How should we model new schema?" -> [DataModeling.md](../DataModeling.md)
- "How should we test changes?" -> `docs/Testing.md`
- "How is this deployed?" -> [Hosting.md](../Hosting.md)
