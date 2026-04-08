# Citations - UX Design and Architecture

Design decisions for how Pinbase handles citations. This is the design — big UX rocks, domain model, key constraints — not an implementation plan.

## The Basic Concept

Contributors write normal Markdown prose and inserts citations using the `[[` wikilink syntax, which triggers the existing autocomplete UI, which will be extended to include citation functionality:

```markdown
The production run was 4,000 units.[[cite:12345]]
```

- `12345` is the ID of a **Citation Instance** — see data model below.
- The marker means "this source is relevant here" — by convention, it supports the preceding sentence or clause.
- Multiple citations on the same sentence are fine: `...4,000 units.[[cite:123]][[cite:456]]`

### Autocomplete UI

Contributors type `[[` to trigger an autocomplete UI that searches for or creates a Citation Source, adds a locator, and inserts the marker.

In the future we can add a Markdown editing toolbar or a WYSIWYG UI on top of this basic approach, but not in v1.

### Point markers

Citations are **point markers** — footnotes inserted at a position in the text, as opposed marking a section of text via a range, or a section-based approach. See [CitationGranularity.md — Decision](CitationGranularity.md#decision) for why we chose this approach.

## Data Model

### Structure

- **Citation Source** — the work or evidence object being cited (a book, flyer, web page, etc.)
- **Citation Instance** — a specific use of a Citation Source at a specific point in the text, with a locator
- **Citation Source Link** — a URL where the reader can inspect a Citation Source

```text
Markdown text
  └── [[cite:12345]]
           │
           ▼
      Citation Instance (id: 12345)
      ├──locator: "p. 30"         (page, timestamp, section, etc.)
      └── citation_source: FK → Citation Source 789
              │
              ▼
         Citation Source (id: 789)
         ├── name: "The Encyclopedia of Pinball"
         ├── type: "book"
         ├── author: "Richard Bueschel"
         └── (type-specific fields)
              ▲
              |
Citation Source Link
├── FK → Citation Source 789
├── url: "https://archive.org/..."
└── label: "archive.org scan"
```

### Citation Source

Represents a work, document, or evidence object. This is independent of where it is cited (which is a Citation Instance).

It's named "Citation Source" to distinguish from the existing claim `Source` concept (IPDB, OPDB, user, etc.) which tracks who added data into system.

#### Citation Sources Are Shared

A single Citation Source can be referenced by many Citation Instances across many pages. When someone cites page 30 of Bueschel and someone else cites page 83, both Citation Instances point at the same Citation Source record.

##### This is a controversial decision

Using shared Citation Sources — rather than having each citation site declare its own source independently — is actually a controversial decision. Wikipedia doesn't do this, though the Wikimedia community wishes it could. See [CitationSharing.md — Recommendation](CitationSharing.md#recommendation) for the full analysis of why Pinbase adopts shared sources and the tradeoffs involved.

##### All Citation Sources are Shared

There's no concept of local-only Citation Sources. If a user creates a one-off Citation Source, it shows up in the autocomplete for everyone.

This will probably get annoying, seeing junk in autocomplete. Post v1, autocomplete could rank and filter in various ways TBD.

#### Citation Source Types

There are different types of Citation Sources. Here's a potential starter list; we'll build one or two Citation types, see how it goes, and expand from there:

| Type     | Additional fields      | Covers                                                                                     |
| -------- | ---------------------- | ------------------------------------------------------------------------------------------ |
| book     | isbn, format, language | Monographs, encyclopedias, reference books                                                 |
| document | language               | Manuals, flyers, patents, press releases                                                   |
| photo    | (none)                 | Photographs used as evidence, whether uploaded to Pinbase or hosted externally             |
| web      | (none)                 | Web articles, forum posts, database pages. Fallback if there's not a more specific source. |

The Citation Source's type drives:

- how the citation is rendered to readers. Examples:
  - book: The Encyclopedia of Pinball. Richard Bueschel. p. 30.
  - video: Roger Sharpe interview. 04:12. [YouTube]
- which fields are shown on edit screens
- how to assist with and validate location input. Examples:
  - a video source might prompt with Timestamp
  - a book source might prompt with Page, Chapter, or Kindle location
  - a flyer source might prompt with Front or Back
  - a URL source may require and validate that it's a URL fragment ("#....")
- autocomplete search behavior. Examples:
  - books may match on author/title/ISBN
  - periodicals may match on publication + issue + article title
  - videos may match on channel/title/date
  - records may match on institution + accession number

See [CitationSourceTypes.md](CitationSourceTypes.md) for the research around this.

#### Citation Source DB model

Citation Source is a single database table/model with a flat set of mostly-optional fields. Every type of Citation Source uses a subset of the same ~12 fields; no type introduces fields alien to the others. See the field inventory in [CitationDomainModel.md](CitationDomainModel.md).

We could have chosen instead to use polymorphic models or a JSONField to capture the differences between types of Citation Sources, but after analysis of the likely Citation Sources, we concluded that they mostly share fields and that it's simpler to have one single table with optional fields.

#### Citation Sources are Hierarchical

Citation Sources are nested:

```text
The Encyclopedia of Pinball
├── 1996 Edition 1
└── 1999 Edition 2
   └── French translation
         ├── Edition 2 hardcover version, French translation
         ├── Edition 2 paperback version, French translation
         └── Edition 2 Kindle version, French translation
```

Citation Source has a `parent` FK to itself, following the same pattern as `Location`. A root source (no parent) represents the abstract work; children are progressively more specific published forms (editions, translations, formats).

Most Citation Sources are simple roots with no children — a flyer, a web page, a museum observation. The hierarchy only fans out when the real world requires it.

See [CitationDomainModel.md](CitationDomainModel.md) for worked examples including books, manuals, and magazines.

##### Citation Sources Don't Inherit Information

Each Citation Source stores its own fields independently. Children do not inherit values from their parent chain.

Inheritance would add a level of conceptual complexity that make the system hard to reason about -- both for people editing as well as AIs trying to build the code. We don't, for example, want to deal with the ambiguity of overriding inherited values.

The create-child UI can pre-fill fields from the parent as a convenience, but the data model treats each record as self-contained.

### Citation Source Link

A way for the reader to inspect a Citation Source: a canonical URL, archive URL, museum-hosted scan, Kindle Store page, etc. Citation Source Link has three fields: FK to Citation Source, url, and label (display text like "archive.org scan" or "IPDB PDF"). These can be enriched later if the system needs to distinguish between link kinds or detect broken links.

### Citation Instance

A Citation Instance is a specific use of a Citation Source at a specific location in the text. It's the thing that the wikilink citation in the markdown points at:

```markdown
The production run was 4,000 units.[[cite:12345]]
```

The Citation Instance carries:

- **FK to Citation Source**
- **Locator within the source** (page number, chapter, timestamp, etc.)
  — The locator is freeform text, not structured data. Real-world locators vary too widely to schema ("page 30", "front", "back, specifications", "timestamp 4:12").

#### Citation Instances aren't shared

Two different markdown files both citing the same page of the same book get their own Citation Instances, even if they might be identical.

#### Citation Instances are immutable

To change a citation (e.g. correct a page number from "p. 30" to "p. 31"), the contributor creates a new Citation Instance and the Markdown text is updated from `[[cite:12345]]` to `[[cite:12346]]`. That text change flows through the claims system as a normal claim revision, so citation history is captured for free — no separate versioning needed for Citation Instance records.

Orphaned Citation Instances (no longer referenced by any text) can be cleaned up lazily or left in place.

#### Reverts restore citation markers with the text

Since citation markers are inline in the Markdown, reverting a text edit reverts the markers too. The Citation Instance records remain in the database — this is correct because the revert itself could be un-reverted in the future, and the Citation Instance would become referenced again.

### Two citation mechanisms, one per content type

Both markdown and scalar fields reference the same Citation Instance records, just attached differently:

| Content type                                       | How citations attach                                       |
| -------------------------------------------------- | ---------------------------------------------------------- |
| Long-form markdown fields (descriptions, articles) | Inline `[[cite:...]]` markers in the Markdown text         |
| Scalar fields (year, manufacturer, player count)   | Citation Instances linked to the claim record (reverse FK) |

Scalar claims can have multiple Citation Instances — a production count confirmed by both a flyer and a trade magazine gets two Citation Instance records, each pointing at its Citation Source.

This is asymmetrical in mechanism because the content is asymmetrical — a year and a multi-paragraph description are fundamentally different. But both use the same Citation Instance and Citation Source entities, so the data model is unified.

From the contributor's perspective:

- Editing a description: write text, type `[[` to attach a source inline.
- Editing a scalar: change the value, add one or more citations through the form.

### Citation vs. claim source

These are different concepts:

- **Claim source** (IPDB, OPDB, user, etc.): who put this data into Pinbase. Provenance.
- **Citation**: what external evidence supports the data being correct. Evidence.

A page that is 90% ingested from IPDB has provenance (we know the data came from IPDB) but no citations (nobody has attached evidence for why the values are correct). Adding a citation would be someone finding the flyer or production record that confirms what IPDB says.

## Citation Seeding

We're going to pre-seed the Citation Source table with a whole bunch of Citation Sources, as described in [CitationSourceSeeding.md](CitationSourceSeeding.md).

## Contributor UX

### Citation Source search and creation

The `[[` autocomplete should make finding an existing Citation Source feel as fast as typing inline:

- **Typeahead** searching across name, author, and aliases — "Bueschel" and "Encyclopedia Pinball" should both find the same record.
- **Recently used Citation Sources** surfaced first — if you're working through a book, you shouldn't search for it every paragraph.
- **Quick-create** that doesn't interrupt the flow — if nothing matches, creating a new Citation Source should be a one-step expansion of the search panel, not a separate page.

### Rich text overlay

A rich text layer over the Markdown can render citation markers as superscript footnote numbers rather than raw `[[cite:...]]` tokens. Contributors working in rich mode see familiar footnote markers; contributors who prefer raw Markdown see the tokens directly. Both are editing the same underlying text.

### Edit note vs. citation

The existing edit note field remains unchanged. It sits alongside citations, not instead of them:

- **Citation**: what evidence supports the content.
- **Edit note**: what changed in this save and why.

"Fixed typo" is a fine edit note and a useless citation. "Williams flyer, 1993" is a useful citation and an incomplete edit note.

### Citations are not required

Contributors can save edits without attaching citations. The system may nudge (e.g. a subtle prompt or quality indicator) but does not enforce. This keeps the contribution barrier low — an edit without a citation is still better than no edit at all.

### Other contributors can add citations to existing text

A common and valuable action: "I didn't write this, but I can confirm it from this flyer." Contributors can add citation markers to existing prose without rewriting it. This is a normal text edit through the claims system — the prose doesn't change, but the Markdown gains `[[cite:...]]` markers.

Other contributors can also revert a citation addition, just like any other edit.

## Reader UX

### Read-side rendering

On the published page:

- Inline citation markers render as small superscript reference numbers.
- A **References** section at the bottom of the article lists all citations with source details.
- Each reference entry shows the evidence type, source details, and locator.
- Where applicable, links to uploaded media, documents, or URLs.
- Clicking a superscript number scrolls to the reference; clicking the back-arrow on the reference scrolls back to the text.

### Unifying scalar and inline citations in read view

The reader-facing References section can draw from both inline text citations and scalar claim citations, presenting them in a single list. The reader does not need to know about the implementation difference.

### Pages with no citations

Nothing. No references section appears. Uncited pages are normal, not incomplete.

### Surfacing claim sources to readers

Claim sources (IPDB, OPDB, user, etc.) are already visible to readers via the Sources tab on each entity page. Citations are a separate concept — they are external evidence supporting the data, not provenance for who entered it. Both are reader-facing.

## Governance of Shared Citations

Governance for shared Citation Sources will be lightweight in v1.

- Anyone with at least one edit may edit any Citation Source and create a new one.
- Editing a shared Citation Source does not require review.
- Citation Source creates and edits appear in the global changes feed at /changes/. They can be filtered in or out of that view.
- Editing a shared Citation Source propagates immediately to all Citation Instances that reference it. The Citation Instances themselves are unchanged; only the shared source metadata updates.
- You cannot re-parent Citation Sources in v1.
- You cannot merge duplicate Citation Sources in v1.
- You can delete a Citation Source if there are no active Citation Instances (meaning Citation Instances actually referenced in the catalog data). This allows for deleting incorrect, empty, spammy, or accidentally created shared sources. I believe this is a hard delete. Any reason it shouldn't be?

This is intentionally permissive. More governance will be added post v1. The v1 system will be a progressively wider soft-launch limited to friends of the museum, so we have scope to improve this gradually.

## Architecture

### Citation is its own Django app

The citation source system -- Citation Source and Citation Source Link -- lives in a standalone `citation` app, separate from both `catalog` and `provenance`. Citation Instance lives in `provenance` because it's coupled with claims.

- `catalog` and `citation` don't know about each other.
- `provenance` knows about `citation`, but `citation` does not know about `provenance`.

Citation Instance lives in `provenance` because it's fairly coupled to it:

- For scalar fields, `CitationInstance` has a FK to `Claim` (so a Claim can have multiple Citation Instances).
- For text fields, `[[cite:123]]` markers in the Markdown are materialized as `RecordReference` rows on save, like other wikilink types. The Citation Instance's Claim FK is null.

### Citation Sources are not claims-controlled

Citation Sources are evidence, not catalog assertions. They support claims; they are not claims themselves. The claims/provenance system that governs catalog fields (where multiple sources can assert conflicting values and the highest-priority source wins) does not apply to citation data.

A Citation Source is reference metadata: "this book exists, it was written by this author, published in this year." That metadata may be corrected by contributors over time, but it does not need conflict resolution, source priority, or the audit machinery that claims provide.

### No Migrations

The database is being deleted and reset with fresh 0001 migrations. So, for example:

- We don't migrate any existing data on the `citation` TextField on Claim.

## Follow-ups

### CitationInstance → CitationSourceLink FK

For web sources, the CitationInstance locator is a URL fragment (e.g. `#section-3`) that must be appended to a CitationSourceLink URL to produce a full deep link. Currently CitationInstance has a FK to CitationSource but no relationship to CitationSourceLink, so the rendering path has to guess which link to pair with the fragment.

**Option A — Optional FK from CitationInstance to CitationSourceLink.** Explicit: the instance says "this fragment belongs to this link." Null for non-web sources where the locator is "p. 30". Needs a cross-FK constraint (the link must belong to the same source). PROTECT on delete enforces link integrity at the DB level.

**Option B — Keep it implicit.** The locator is just text. Rendering logic picks the "best" link from the source (first? primary? only one for most web sources). Simpler model, fuzzier semantics.

This also affects whether CitationSourceLinks can be deleted — if instances reference them via FK, deletion is blocked by PROTECT. Until this is resolved, link deletion is not exposed in the API.

### Edit-count permission gate

The governance section says "anyone with at least one edit" can create/edit Citation Sources. The v1 API uses plain session auth (`django_auth`), matching every other write endpoint in the project. No endpoint currently enforces an edit-count threshold. This should be designed as a cross-cutting permission class when it's needed, not bolted onto one API in isolation.

### Changes feed integration

The governance section says Citation Source creates and edits appear in the `/changes/` feed. The changes feed doesn't exist yet as an API-driven feature for any entity type — it's admin-side only. This needs holistic design across all entity types before citation editing goes to real contributors.

### Extract `_clean_and_save` to `apps/core`

The citation API introduced `_clean_and_save()` — a helper that calls `full_clean()` then `save()`, converting both `ValidationError` and `IntegrityError` into `HttpError(422)`. This is the first standard CRUD API in the project (all others go through the claims system). When a second CRUD API appears, this helper should move to `apps/core/` rather than being copied or imported across app boundaries.

### Investigate `validate_no_mojibake` gap in claims path

The `validate_no_mojibake` validators on model fields only fire via `full_clean()`. The claims system writes through `Claim.objects.assert_claim()` → `validate_claim_value()`, which does not call `full_clean()` on the target model. This means mojibake could theoretically slip through claim-controlled text fields. Worth investigating whether the claims validation path should run mojibake checks on string values.

### Investigate auto-`full_clean()` on `TimeStampedModel.save()`

Django's `create()` and `save()` skip `full_clean()` by default — Python-level validators (`validate_no_mojibake`, `URLField` format, `MinValueValidator`, etc.) only fire if `full_clean()` is explicitly called. CHECK constraints catch some of this at the DB level, but validators like `validate_no_mojibake` have no DB equivalent.

This is a pit-of-failure API: the wrong thing (`create()` without validation) is the easy thing, and the right thing (instantiate → `full_clean()` → `save()`) requires the caller to remember every time. During the citation seeding work, an AI agent made the same mistake three times in one planning session — first using `create()` without `full_clean()`, then calling `full_clean()` after `create()` (which already wrote the invalid row), and finally getting the order right only after explicit review. If an agent iterating on a plan with a human reviewer makes this mistake systematically, contributors writing management commands or API endpoints will too.

A potential fix: override `save()` on `TimeStampedModel` to call `self.full_clean()` automatically, so every model in the project validates on every save by default. This would make the citation API's `_clean_and_save()` helper unnecessary and close the mojibake gap in the claims path (see above).

**Needs investigation before adopting:**

- Django deliberately doesn't do this — there may be good reasons (performance, circular save issues, `QuerySet.update()` semantics). Research why Django made this choice.
- Could surface latent validation failures in existing code paths that currently skip validation.
- `bulk_create()` / `bulk_update()` don't call `save()`, so they'd still skip validation — but that's an explicit opt-in to raw performance, which is acceptable.
- The CLAUDE.md currently says "full_clean() is optional; CHECK constraints are not" — that guidance would need updating.
- Run the full test suite after the change to see what breaks.

### Pre-emptive archiving via Wayback Machine

Wikipedia encourages [pre-emptive archiving](https://en.wikipedia.org/wiki/Wikipedia:Citing_sources/Further_considerations#Pre-emptive_archiving) of cited URLs because web sources aren't forever. The Wayback Machine has an API (`https://web.archive.org/save/{url}`) that snapshots a page on demand. A background job could:

1. When a web CitationSource is created or a CitationSourceLink is added, fire an async task
2. Hit the Wayback Machine save API to ensure a recent snapshot exists
3. Store the resulting `https://web.archive.org/web/{timestamp}/{url}` as a new CitationSourceLink with `link_type="archive"`

The API is slow (seconds per request) so this must be async. It's also rate-limited, so the job should be debounced and respect backoff. This depends on the `link_type` field existing (see above) so the system can distinguish human-curated links from machine-created archive snapshots.

**Open questions:**

- Should we also periodically re-snapshot existing links (e.g. monthly) to catch content drift?
- Should we snapshot at citation-creation time (when a CitationInstance is created) or at source-creation time (when a CitationSourceLink is added)?
- The Wayback Machine API sometimes fails silently or returns old snapshots — how do we handle that?
- Archive.org's terms of service and rate limits need investigation before building this.

### Hierarchical source navigation in autocomplete

The citation source search returns a flat list of all matching sources, including parents and children. For a source like "The Encyclopedia of Pinball" with multiple editions, the search results show 5-6 near-identical entries that are easy to confuse. The hierarchy (parent → editions → translations) exists in the data model but isn't surfaced in the autocomplete UI.

The autocomplete should present hierarchical sources in a way that lets contributors drill into the right edition without being overwhelmed by near-duplicates. Some possible approaches:

- **Group by parent**: Search results show only root sources (or the highest matching ancestor). Selecting one expands inline to show its children, then the contributor picks the specific edition. Adds one click but keeps the list clean.
- **Indent children**: Show all results but visually nest children under their parent. The contributor sees the hierarchy at a glance without an extra click, but the list gets long.
- **Parent with count badge**: Show "The Encyclopedia of Pinball (4 editions)" — selecting it opens a sub-list. Compact, but adds a navigation step.

Key design question: when citing, do contributors usually know which specific edition they want (common for books — "I have the 1996 edition"), or do they start from the parent and narrow down? The answer may differ by source type: books have meaningful editions, web sources rarely have hierarchy at all.

This affects both the search API (which currently returns a flat list ordered by name) and the CitationAutocomplete UI (which renders results as a flat list of DropdownItems).

### Recently used sources in autocomplete

The Contributor UX section describes "Recently used Citation Sources surfaced first" as part of the autocomplete experience. This is deferred — the v1 search endpoint returns results ordered by name only. Adding recently-used ranking requires tracking per-user citation activity and merging it into the search results.

### Standardize frontend API calls on the typed client

`frontend/src/lib/api/link-types.ts` uses raw `fetch()` with hand-written types (`LinkType`, `LinkTarget`) for the wikilink autocomplete endpoints. Every other API call in the frontend uses the openapi-fetch `client` from `client.ts` with generated types from `schema.d.ts`. When the `flow` field was added to the link types API, the hand-written `LinkType` type had to be manually updated to match the backend — exactly the kind of drift that generated types prevent.

The fix: delete the hand-written types and raw fetch calls in `link-types.ts`, replace with `client.GET()` calls. For example:

```typescript
// Before (hand-written types, raw fetch)
export type LinkType = {
  name: string;
  label: string;
  description: string;
  flow: "standard" | "custom";
};
const resp = await fetch("/api/link-types/");
cachedTypes = (await resp.json()) as LinkType[];

// After (generated types, typed client)
const { data } = await client.GET("/api/link-types/");
cachedTypes = data ?? [];
```

The module-level cache and `searchLinkTargets` function stay, they just use `client.GET` internally. Tests in `link-types.test.ts` would need to mock `client` instead of `globalThis.fetch`.

### Batch endpoint deprecation

The batch endpoint (`GET /api/citation-instances/batch/?ids=...`) is now only used by `MarkdownTextArea` for edit preview — all page renders use inline citation data from the page API. If edit preview is ever reworked to use a server-side preview endpoint (which would go through the same render pipeline), the batch endpoint becomes dead code and can be removed.

### Scalar citation references

The references section currently only includes inline `[[cite:N]]` markers from rendered markdown. Scalar field citations (e.g., "year claimed by source X") are not shown. When scalar citations are surfaced on reader-facing pages, they'll need either: (a) to feed into the existing per-field references section, or (b) a page-level aggregation that merges citations from all fields and scalar claims into a single bibliography. The inline numbering (`index`) is assigned during markdown rendering, so scalar citations would need a separate numbering scheme or a two-pass approach. This is a design decision for that future work.

### Svelte component tests

WikilinkAutocomplete and MarkdownTextArea now have DOM tests (`@testing-library/svelte` + jsdom) covering keyboard navigation, back-navigation, focus management, link insertion, debounce, ARIA attributes, and close behavior. See `docs/Testing.md` for established patterns.

**Remaining test targets:**

- **Edit forms** — claim editing forms have complex validation and submission flows that are only verified manually.

### Type-picker `aria-activedescendant` gap

The search stage has full ARIA combobox wiring (`role="combobox"`, `aria-activedescendant`, `aria-controls`), but the type-picker stage does not. During type picking, focus stays on the textarea and keyboard events are forwarded via `handleExternalKeydown`. The textarea has no `aria-activedescendant` pointing to the highlighted type-picker option, so screen readers don't announce which option is selected during keyboard navigation.

Fixing this requires cross-component coordination: WikilinkAutocomplete would need to expose the active type-picker option's ID, and MarkdownTextArea would need to set `aria-activedescendant` on the textarea when the dropdown is open in type-picker stage. This is the same general pattern as the search stage, but spanning two components instead of being self-contained.
