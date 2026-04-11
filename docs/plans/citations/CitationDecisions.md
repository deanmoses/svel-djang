# Citation Decisions

This document captures the decision process behind the citation system after consolidating a larger set of exploratory notes. It keeps the durable conclusions and drops implementation-level planning.

## The Problem

Pinbase is trying to be a trusted encyclopedia, not just a list of facts. In pinball history, unattributed claims quickly blur into rumor, repeated lore, or database cargo-culting. Citations matter because they let a reader or editor answer two questions quickly:

- what external evidence supports this claim
- how can I inspect that evidence myself

That is distinct from Pinbase's provenance system. Provenance answers who put data into Pinbase. Citations answer what external evidence supports it.

## What Comparable Systems Taught Us

The main lessons from Wikipedia, MediaWiki-derived communities, and adjacent knowledge systems were straightforward:

- Verifiability is worth copying.
- Inline citation bureaucracy is not.
- Reuse matters, but mandatory central bibliographies create friction.
- Automatic citation helpers are only good when they have strong metadata extraction and a credible manual fallback.

The key product takeaway was that Pinbase should preserve the verification loop without requiring contributors to think like librarians or template engineers during ordinary editing.

## Product Constraints

Several constraints shaped the design:

- Citation authoring has to stay cheap at the moment of editing.
- Contributors often know only part of the source identity.
- The system has to support informal and heterogeneous evidence, not just clean academic-style references.
- Readers need evidence they can inspect, not only opaque metadata.
- Shared records should improve consistency without blocking contribution when reuse is unclear.

## Decisions

### Citations are evidence, not provenance

Pinbase keeps citations separate from claim provenance.

- Provenance tracks which source or user asserted data into Pinbase.
- Citations track the external evidence that supports a claim or passage.

That separation matters because a claim can come from IPDB while the evidence that validates it is a flyer, manual, interview, or museum-held document.

### Use point citations, not text ranges

Pinbase uses point citations, inserted at a position in the text, rather than wrapping exact text ranges.

Ranges look more precise, but in practice they impose too much editorial discipline, become awkward with multi-source sentences, and create misleadingly precise-looking markup. Point citations are more honest about the level of precision contributors will reliably maintain.

### Separate source, instance, and link

The data model distinguishes:

- `Citation Source`: the work or evidence object being cited
- `Citation Instance`: one use of that source, usually with a locator
- `Citation Source Link`: one way to inspect that source

This separation avoids collapsing unlike things into one record. The same book can be cited on multiple pages, and the same source can have multiple access links without becoming multiple sources.

### Citation sources are shared, but reuse should assist rather than gate authoring

Pinbase wants reusable citation sources because they improve consistency, deduplication, and long-term maintenance. But the system should not force contributors into a strict centralized bibliography workflow before they can save.

The rule is:

**Centralization should assist citation reuse, not gate citation authoring.**

That means:

- shared citation sources are the long-term model
- duplicate detection is important
- perfect deduplication is not a prerequisite for saving
- editorial cleanup and merging can happen later

### Citation sources may be hierarchical

Some sources are simple one-off records. Others are source families: work and edition, publication and issue, documentation set and specific manual. Pinbase therefore allows citation sources to have a parent source.

The hierarchy represents identity, not locator position. Page numbers, timestamps, sections, and similar references belong on the citation instance, not as deeper source nodes.

### Keep source types pragmatic

Source types exist to drive product behavior:

- reader rendering
- edit fields
- locator prompts and validation
- search behavior

They should therefore be pragmatic and few, not an attempt at a perfect universal bibliography ontology. A broad fallback type remains important.

### Search existing first, then help create

The citation flow should begin with one unified input. Contributors should be able to type a search query or paste evidence such as a URL, ISBN, or DOI into the same entry point.

The decision path is:

1. Search for an existing source first.
2. If no strong match exists and the input looks like evidence, try to build a draft source automatically.
3. Let the user confirm or edit the draft before creation.

This keeps reuse primary without forcing contributors to choose between "manual" and "automatic" modes up front.

### Pre-seed important sources where feasible

For major source families that Pinbase knows it will cite repeatedly, pre-seeding is worth doing. It reduces duplicate creation, improves autocomplete quality, and makes shared citation infrastructure more likely to stick.

This is especially attractive for bounded pinball-specific corpora such as books, magazines, manuals, and major websites.

## What We Intentionally Dropped

The old citation planning folder included detailed notes on:

- state machine refactors
- extractor module layout
- implementation sequencing
- UX research branches that no longer affect the final design

Those details were useful while building, but they are not the right level for long-lived planning docs. The remaining companion document, [CitationsDesign.md](CitationsDesign.md), now carries the high-level design that follows from these decisions.
