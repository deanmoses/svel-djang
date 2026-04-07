# Citations - UX Design and Architecture

Design decisions for how Pinbase handles citations. This is the design — big UX rocks, domain model, key constraints — not an implementation plan.

## The Basic Concept

Contributors write normal Markdown prose and inserts citations using the `[[` wikilink syntax, which triggers the existing autocomplete UI, which will be extended to include citation functionality:

```markdown
The production run was 4,000 units.[[cite:id:12345]]
```

- `12345` is the ID of a **Citation Instance** — see data model below.
- The marker means "this source is relevant here" — by convention, it supports the preceding sentence or clause.
- Multiple citations on the same sentence are fine: `...4,000 units.[[cite:id:123]][[cite:id:456]]`

### Autocomplete UI

Contributors type `[[` to trigger an autocomplete UI that searches for or creates a Citation Source, adds a locator, and inserts the marker.

In the future we can add a Markdown editing toolbar or a WYSIWYG UI on top of this basic approach, but not in v1.

### Point markers

Citations are **point markers** — footnotes inserted at a position in the text, as opposed marking a section of text via a range, or a section-based approach. See [CitationGranularity.md — Decision](CitationGranularity.md#decision) for why we chose this approach.

## Data Model

### Structure

- **Citation Source** — the work or evidence object being cited (a book, flyer, web page, etc.)
- **Citation Instance** — a specific use of a Citation Source at a specific point in the text, with a locator
- **Access Link** — a URL where the reader can inspect a Citation Source

```text
Markdown text
  └── [[cite:id:12345]]
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
Access Link
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

#### Citation Source Types

There are different types of Citation Sources. Here's a potential starter list; this has not yet been finalized, and would almost certainly grow as time goes on:

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

#### Periodical `volume` and `issue` are structured fields

For periodical sources, `volume` and `issue` are structured fields, not part of the freeform title. The display layer assembles them into a formatted label (e.g., "Vol. 4, No. 15 — August 15, 1978") for autocomplete and read-side rendering.

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

Inheritance adds a level of conceptual complexity that make the system hard to reason about -- both for people editing as well as AIs trying to build the code. We don't, for example, want to deal with the ambiguity of overriding inherited values.

The create-child UI can pre-fill fields from the parent as a convenience, but the data model treats each record as self-contained.

### Access Link

A way for the reader to inspect a Citation Source: a canonical URL, archive URL, museum-hosted scan, Kindle Store page, etc. Access Link has three fields: FK to Citation Source, url, and label (display text like "archive.org scan" or "IPDB PDF"). These can be enriched later if the system needs to distinguish between link kinds or detect broken links.

### Citation Instance

A Citation Instance is a specific use of a Citation Source at a specific location in the text. It's the thing that the wikilink citation in the markdown points at:

```markdown
The production run was 4,000 units.[[cite:id:12345]]
```

The Citation Instance carries:

- **FK to Citation Source**
- **Locator within the source** (page number, chapter, timestamp, etc.)
  — The locator is freeform text, not structured data. Real-world locators vary too widely to schema ("page 30", "front", "back, specifications", "timestamp 4:12").

#### Citation Instances aren't shared

Two different markdown files both citing the same page of the same book get their own Citation Instances, even if they might be identical.

#### Citation Instances are immutable

To change a citation (e.g. correct a page number from "p. 30" to "p. 31"), the contributor creates a new Citation Instance and the Markdown text is updated from `[[cite:id:12345]]` to `[[cite:id:12346]]`. That text change flows through the claims system as a normal claim revision, so citation history is captured for free — no separate versioning needed for Citation Instance records.

Orphaned Citation Instances (no longer referenced by any text) can be cleaned up lazily or left in place.

#### Reverts restore citation markers with the text

Since citation markers are inline in the Markdown, reverting a text edit reverts the markers too. The Citation Instance records remain in the database — this is correct because the revert itself could be un-reverted in the future, and the Citation Instance would become referenced again.

### Two citation mechanisms, one per content type

Both markdown and scalar fields reference the same Citation Instance records, just attached differently:

| Content type                                       | How citations attach                                       |
| -------------------------------------------------- | ---------------------------------------------------------- |
| Long-form markdown fields (descriptions, articles) | Inline `[[cite:id:...]]` markers in the Markdown text      |
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

## Contributor UX

### Citation Source search and creation

The `[[` autocomplete should make finding an existing Citation Source feel as fast as typing inline:

- **Typeahead** searching across title, author, and aliases — "Bueschel" and "Encyclopedia Pinball" should both find the same record.
- **Recently used Citation Sources** surfaced first — if you're working through a book, you shouldn't search for it every paragraph.
- **Quick-create** that doesn't interrupt the flow — if nothing matches, creating a new Citation Source should be a one-step expansion of the search panel, not a separate page.

### Rich text overlay

A rich text layer over the Markdown can render citation markers as superscript footnote numbers rather than raw `[[cite:id:...]]` tokens. Contributors working in rich mode see familiar footnote markers; contributors who prefer raw Markdown see the tokens directly. Both are editing the same underlying text.

### Edit note vs. citation

The existing edit note field remains unchanged. It sits alongside citations, not instead of them:

- **Citation**: what evidence supports the content.
- **Edit note**: what changed in this save and why.

"Fixed typo" is a fine edit note and a useless citation. "Williams flyer, 1993" is a useful citation and an incomplete edit note.

### Citations are not required

Contributors can save edits without attaching citations. The system may nudge (e.g. a subtle prompt or quality indicator) but does not enforce. This keeps the contribution barrier low — an edit without a citation is still better than no edit at all.

### Other contributors can add citations to existing text

A common and valuable action: "I didn't write this, but I can confirm it from this flyer." Contributors can add citation markers to existing prose without rewriting it. This is a normal text edit through the claims system — the prose doesn't change, but the Markdown gains `[[cite:id:...]]` markers.

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

## Architecture

### Citation is its own Django app

The citation source system -- Citation Source and Access Link -- lives in a standalone `citation` app, separate from both `catalog` and `provenance`. Citation Instance lives in `provenance` because it's coupled with claims.

- `catalog` and `citation` don't know about each other.
- `provenance` knows about `citation`, but `citation` does not know about `provenance`.

Citation Instance lives in `provenance` because it's fairly coupled to it:

- For scalar fields, `CitationInstance` has a FK to `Claim` (so a Claim can have multiple Citation Instances).
- For text fields, `[[cite:id:123]]` markers in the Markdown are materialized as `RecordReference` rows on save, like other wikilink types. The Citation Instance's Claim FK is null.

### Citation Sources are not claims-controlled

Citation Sources are evidence, not catalog assertions. They support claims; they are not claims themselves. The claims/provenance system that governs catalog fields (where multiple sources can assert conflicting values and the highest-priority source wins) does not apply to citation data.

A Citation Source is reference metadata: "this book exists, it was written by this author, published in this year." That metadata may be corrected by contributors over time, but it does not need conflict resolution, source priority, or the audit machinery that claims provide.

### No Migrations

The database is being deleted and reset with fresh 0001 migrations. So, for example:

- We don't migrate any existing data on the `citation` TextField on Claim.
