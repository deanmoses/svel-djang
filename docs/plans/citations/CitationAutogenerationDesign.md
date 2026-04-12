# Citation Autogeneration Design

This document describes the planned automatic source-draft flow for citations. It is intentionally future-facing: parts of it have not been implemented yet.

## Status

Pinbase has a backend recognition layer (built April 2026) that handles:

- **Extractor registry** (`backend/apps/citation/extractors.py`): URL pattern matching and identifier validation for IPDB, OPDB, and future schemes. Keyed by `CitationSource.identifier_key`.
- **Search recognition**: the `/api/citation-sources/search/` endpoint recognizes pasted URLs (extractor match, full URL child-link match, domain matching against homepage links) and returns structured recognition metadata alongside search results.
- **Identifier-based child creation**: the create endpoint validates identifiers through extractors, auto-builds canonical URLs and child names.
- **DB-level deduplication**: `CitationSource.identifier` field with `UNIQUE(parent, identifier)` constraint prevents duplicate children.

What is not implemented yet is the **extraction layer for external metadata lookups** — calling external services (ISBN APIs, DOI resolvers, page metadata scrapers) and returning proposed `CitationSource` drafts for confirmation.

## Goal

Citation entry should accept evidence-like input such as:

- ISBN
- DOI
- known-site URL
- generic URL

If search does not find an existing source, Pinbase should try to turn that evidence into a proposed new source draft instead of forcing the contributor into manual data entry.

The important constraint is that this should help source creation, not silently bypass editorial review.

## Product Shape

The intended flow is:

1. User searches or pastes evidence into the citation input.
2. Pinbase searches for an existing source first.
3. If there is no strong existing match and the input looks like evidence, Pinbase runs extraction.
4. Extraction returns either:
   - a proposed source draft
   - an existing-source match
   - a structured failure
5. The user confirms or edits the draft before creation.

## Design Principles

### Backend, not frontend

The extraction layer should live on the Django side, not in the Svelte UI.

Reasons:

- external HTTP belongs on the server
- rate limiting and caching belong on the server
- API keys, if any, belong on the server
- source creation and validation already live on the server

### Drafts, not auto-create

Extraction should produce a `CitationSource` draft, not silently create records. The user should still confirm or edit what will be saved.

### Known extractors first

Generic extraction is a weak fallback. Known identifiers and known sites should get dedicated extractors first.

Examples:

- ISBN -> book metadata
- DOI -> publication metadata
- `ipdb.org` URL -> site-specific source draft
- generic URL -> sparse fallback based on page metadata

### Reuse before creation

Extraction is not the first step. Search for an existing source should always run first. Extraction only helps when reuse fails.

## Proposed System Shape

The future backend layer should have three responsibilities:

- classify the input
- run the right extractor
- normalize the result into a draft shape used by citation-source creation

Conceptually:

```text
raw input
  -> input classification
  -> extractor selection
  -> extracted metadata
  -> normalized CitationSource draft
```

The extractor set should stay pragmatic and incremental. It does not need a grand plugin framework on day one, but it should not require rewriting the whole flow every time a new source family is added.

## First Useful Cases

The first high-value extraction targets, with current status:

- **IPDB/OPDB URL recognition** — implemented via extractor registry
- **Domain-based source matching** — implemented via homepage link matching
- **Full URL child-link matching** — implemented for re-citation of known pages
- ISBN lookup for books — not yet implemented (ISBN text search exists, but no external metadata lookup)
- DOI lookup for publications — not yet implemented
- generic URL metadata fallback — not yet implemented

## Failure Behavior

Extraction failures should be normal and explicit.

If extraction fails, the user should get a clear next step:

- use an existing result if one was found
- continue with manual source creation
- revise the pasted input

The system should not make extraction feel magical or guaranteed.

## Relationship To Current Design

This design is a planned extension of the citation flow described in [CitationsDesign.md](CitationsDesign.md).

Today’s identifier parsing and guided child-source behavior are a stopgap in that direction, not the completed architecture.
