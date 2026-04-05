# Citations: UX Design and Architecture

Design decisions for how Pinbase handles citations. This is the design — UX, data model, key constraints — not an implementation plan.

See [Citations.md](Citations.md) for the research and business case.

## Core Concept

Contributors write normal Markdown prose. Citations are attached through a structured autocomplete UI using the existing `[[` convention. The system stores citation markers inline in the text, giving Wikipedia's robustness of attachment without Wikipedia's authoring pain.

Later we could add a Markdown editing toolbar or wrap a WYSIWYG UI on top of that, but not in v1.

## Inline Citation Format

Citations are **point markers** — a footnote inserted at a position in the text:

```text
The production run was 4,000 units.[[cite:id:12345]]
```

- `12345` is the ID of a **citation instance** (not a citation source — see data model below).
- The marker means "this source is relevant here" — by convention, it supports the preceding sentence or clause.
- Multiple citations on the same sentence are fine: `...4,000 units.[[cite:id:123]][[cite:id:456]]`

### Why points, not ranges

We considered range-based citations (`[[cite-start:id:X]]...[[cite-end]]`) that would wrap specific text, making scope explicit. Ranges are theoretically more precise, but three practical problems make them unworkable. See [CitationGranularity.md](CitationGranularity.md) for the full analysis. In short:

1. **Multi-source sentences.** A sentence drawing on three sources needs three ranges — more markup than prose. Contributors either wrap the whole sentence with one "main" source (a lie) or stack all three (source soup, no better than points).
2. **Interleaving truths.** When a new source confirms facts already cited by different ranges, it's unrepresentable without nesting or overlapping — which creates parsing and UX nightmares.
3. **People are lazy.** Precise ranges require selecting small text chunks. Contributors trained by Wikipedia will select whole sentences or paragraphs, producing imprecise ranges that _look_ precise to readers — worse than honest point citations.

Point citations are what Wikipedia uses, proven at scale, and honest about their granularity. The reader understands that a footnote at end-of-sentence means "roughly this sentence."

## Data Model

### Three-level structure

```text
Markdown text
  └── [[cite:id:12345]]
           │
           ▼
      Citation Instance (id: 12345)
      ├── citation_source: FK → CitationSource
      ├── locator: "p. 30"         (page, timestamp, section, etc.)
      └── (instance-specific metadata)
              │
              ▼
         CitationSource (id: 789)
         ├── type: "book"
         ├── title: "The Encyclopedia of Pinball"
         ├── author: "Richard Bueschel"
         └── (type-specific fields)
```

### Citation Source

A first-class reusable entity. Represents a work, document, or evidence object independent of where it is cited. Named "Citation Source" to distinguish from the existing claim `source` field (IPDB, OPDB, user, etc.) which tracks who put data into Pinbase.

A single citation source can be referenced by many citation instances across many pages. When someone cites page 30 of Bueschel and someone else cites page 83, both citation instances point at the same citation source record.

Benefits of reusability:

- Enter citation source metadata once, reuse everywhere.
- "Show me every claim backed by this citation source" is a simple query.
- If a citation source is corrected or discredited, you can find all affected pages.
- Uploaded media (flyer scans, photos) are already assets in the system and naturally become citation sources.

**Citation source types** (recommended initial set):

- Web page / URL
- Book or magazine
- Flyer / manual / document
- Uploaded photo or scan
- Uploaded or URL-referenced video
- Museum record
- Interview / correspondence
- In-person observation
- Other

Each type may have type-specific fields (URL for web pages, author/publisher/ISBN for books, observer/date for observations, videos have a timestamp locator, etc.). The exact schema is an implementation decision.

### Citation Instance

The join between a citation source and its use at a specific location in the text. Carries:

- FK to citation source
- Locator within the source (page number, chapter, timestamp, etc.)
- Any use-specific metadata

This separation means two people citing different pages of the same book share the citation source but have distinct citation instances with different locators.

**Citation instances are immutable.** To change a citation (e.g. correct a page number from "p. 30" to "p. 31"), the contributor creates a new citation instance and the Markdown text is updated from `[[cite:id:12345]]` to `[[cite:id:12346]]`. That text change flows through the claims system as a normal claim revision, so citation history is captured for free — no separate versioning needed for citation instance records. Orphaned citation instances (no longer referenced by any text) can be cleaned up lazily or left in place.

### Two citation mechanisms, one per content type

Both text and scalar fields reference the same citation instance records, just attached differently:

| Content type                                     | How citations attach                                       |
| ------------------------------------------------ | ---------------------------------------------------------- |
| Long-form text fields (descriptions, articles)   | Inline `[[cite:id:...]]` markers in the Markdown text      |
| Scalar fields (year, manufacturer, player count) | Citation instances linked to the claim record (reverse FK) |

Scalar claims can have multiple citation instances — a production count confirmed by both a flyer and a trade magazine gets two citation instance records, each pointing at its citation source.

This is asymmetrical in mechanism because the content is asymmetrical — a year and a multi-paragraph description are fundamentally different. But both use the same citation instance and citation source entities, so the data model is unified.

From the contributor's perspective:

- Editing a description: write text, type `[[cite:` to attach a source inline.
- Editing a scalar: change the value, add one or more citations through the form.

### Citation vs. claim source

These are different concepts:

- **Claim source** (IPDB, OPDB, user, etc.): who put this data into Pinbase. Provenance.
- **Citation**: what external evidence supports the data being correct. Evidence.

A page that is 90% ingested from IPDB has provenance (we know the data came from IPDB) but no citations (nobody has attached evidence for why the values are correct). Adding a citation would be someone finding the flyer or production record that confirms what IPDB says.

## Contributor UX

### Writing flow

The editing flow is: write first, cite second.

1. Write or edit Markdown prose in the editor.
2. Type `[[cite:` to trigger the citation autocomplete.
3. Search for an existing citation source or create a new one.
4. Add a locator if needed (page number, timestamp, etc.).
5. The editor inserts `[[cite:id:12345]]` at the cursor position.

### Citation source search and creation

The `[[cite:` autocomplete should make finding an existing citation source feel as fast as typing inline:

- **Typeahead** searching across title, author, and aliases — "Bueschel" and "Encyclopedia Pinball" should both find the same record.
- **Recently used citation sources** surfaced first — if you're working through a book, you shouldn't search for it every paragraph.
- **Quick-create** that doesn't interrupt the flow — if nothing matches, creating a new citation source should be a one-step expansion of the search panel, not a separate page.

### Rich text overlay

A rich text layer over the Markdown can render citation markers as superscript footnote numbers rather than raw `[[cite:id:...]]` tokens. Contributors working in rich mode see familiar footnote markers; contributors who prefer raw Markdown see the tokens directly. Both are editing the same underlying text.

### Edit note vs. citation

The existing edit note field remains unchanged. It sits alongside citations, not instead of them:

- **Citation**: what evidence supports the content.
- **Edit note**: what changed in this save and why.

"Fixed typo" is a fine edit note and a useless citation. "Williams flyer, 1993" is a useful citation and an incomplete edit note.

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

TBD: whether pages with zero citations show nothing, a subtle quality indicator, or an invitation to add sources. This is a behavioral design decision that should be informed by how we want to shape contributor culture.

## Behavioral Decisions

### Citations are not required

Contributors can save edits without attaching citations. The system may nudge (e.g. a subtle prompt or quality indicator) but does not enforce. This keeps the contribution barrier low — an edit without a citation is still better than no edit at all.

### Other contributors can add citations to existing text

A common and valuable action: "I didn't write this, but I can confirm it from this flyer." Contributors can add citation markers to existing prose without rewriting it. This is a normal text edit through the claims system — the prose doesn't change, but the Markdown gains `[[cite:id:...]]` markers.

Other contributors can also revert a citation addition, just like any other edit.

### Reverts restore citation markers with the text

Since citation markers are inline in the Markdown, reverting a text edit reverts the markers too. The citation instance records remain in the database — this is correct because the revert itself could be un-reverted in the future, and the citation instance would become referenced again. Orphaned instances are harmless and can be cleaned up lazily if needed.

## Open Design Questions

These are questions we've identified but have not yet resolved:

### Data model

- **Citation source entity schema**: exact fields per citation source type. Implementation decision, but the set of types should be validated against real contributor workflows.

### Display

- **Surfacing claim sources to readers**: claim source (IPDB, OPDB, etc.) is provenance, not citation. Should readers see it anywhere, or is it purely internal? A page with "Source: IPDB" and no citations is honest about its provenance even without evidence.
- **Zero-citation pages**: what the reader sees when a page has no citations. This shapes whether citations feel like an invitation or an obligation.
