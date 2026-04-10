# Citation Source Extraction Design

High-level architecture for automatic citation source extraction. Implements the product direction described in [CitationEditUXImprovements.md](CitationEditUXImprovements.md).

## Summary

When a user pastes evidence (URL, ISBN, DOI) into the citation input and no existing source matches, the system extracts metadata from external services and shapes it into a proposed CitationSource draft. The user confirms or edits the draft before it becomes a real source.

## Where It Lives

Extraction lives inside the `citation` app as an `extraction/` module, following the same pattern as catalog ingestion living inside `catalog`.

```text
backend/apps/citation/
  extraction/
    __init__.py
    classify.py          # input classification (ISBN, DOI, URL, text)
    chain.py             # extractor chain runner
    extractors/
      __init__.py
      isbn.py            # Open Library / Google Books
      doi.py             # CrossRef
      ipdb.py            # IPDB site-specific
      generic_url.py     # OG tags, JSON-LD fallback
    draft.py             # CitationSourceDraft shape
  api/
    extract.py           # the /extract/ endpoint
```

## Source Hierarchy

CitationSources are hierarchical. The hierarchy represents **identity** — which specific edition, which specific page on a site — not position within a source (that's what locators are for).

Examples:

- **Books**: The abstract work is the parent. Each ISBN-identified edition is a child. A French Kindle edition is a child of the French edition (or of the abstract work if editions aren't subdivided). Page number is a locator on the CitationInstance, not a level in the hierarchy.
- **IPDB**: IPDB-the-database is the parent source. Each machine page (identified by IPDB machine ID) is a child source. A specific table or section on that page would be a locator, if ever needed.

This means extraction sometimes creates a **child source under an existing parent**, not a top-level source. The draft shape includes an optional `parent` reference. The extractor is responsible for:

1. Determining whether the input belongs under an existing parent (e.g., ISBN → book work, IPDB URL → IPDB parent).
2. Checking whether the child source already exists (dedup).
3. If not, producing a draft positioned in the hierarchy.

### Internal Cross-Reference vs. External Fetch

Not all extraction requires live external requests. Two modes:

- **External fetch**: ISBN → Open Library, DOI → CrossRef, generic URL → HTML scrape. Goes out to the internet.
- **Internal cross-reference**: IPDB ID → our already-ingested IPDB data. No live fetch needed (and IPDB blocks bots anyway). The extractor matches against data we already have in the database.

The extractor interface is the same in both cases. The difference is where the data comes from.

### Parent-Only Sources

Some sources are containers — you never cite them directly, you always cite a specific child. IPDB-the-database is not a citation; IPDB machine page 4836 is. Similarly, the abstract work "The Encyclopedia of Pinball" is not what you cite — you cite a specific ISBN-identified volume.

The system needs to know which sources are parent-only so the UI can enforce "don't stop here, go one level deeper." This is a property of the CitationSource itself, not the extraction system — likely a flag or convention on the model.

## Steel Thread

Two paths exercise the full system end to end:

### Path 1: Paste IPDB URL → automatic child source

1. User pastes `https://www.ipdb.org/machine.cgi?id=4836` into the citation input.
2. Search runs first — no existing child source for IPDB machine 4836.
3. Input classification recognizes a URL. Extract endpoint is called.
4. IPDB extractor matches the URL pattern, extracts machine ID 4836.
5. Cross-references against ingested IPDB data (no live fetch).
6. Finds the IPDB parent source, checks for an existing child — none.
7. Returns a draft for a new child source under IPDB, pre-filled with the machine name from ingested data.
8. User confirms. Child source is created. Citation instance is attached to the claim.

### Path 2: Search "IPDB" → guided child source

1. User types "IPDB" into the citation input.
2. Search finds the IPDB parent source.
3. UI recognizes IPDB is a parent-only source — the user can't cite it directly.
4. UI prompts for a specific IPDB machine: "Enter an IPDB URL or machine ID."
5. User types `4836` or pastes a URL.
6. Because the user already selected the IPDB parent, a bare number is unambiguous — it's an IPDB machine ID.
7. Same extraction flow as Path 1 from step 5 onward.
8. User confirms. Child source is created. Citation instance is attached to the claim.

Path 1 is fully automatic — one paste, one confirmation. Path 2 is guided — the user tells the system which source family, then identifies the specific child. Both end at the same place: a child source under the IPDB parent.

## Why Extraction Lives on the Backend

Extraction happens **on the Django backend**, not in the frontend.

Reasons:

- Extractors call external APIs (Open Library, CrossRef, remote HTML) that require server-side HTTP, API keys, and rate limiting.
- The CitationSource model and its validation logic already live in Django.
- The frontend stays thin: send raw input, receive either search results or a draft.

Note: the citation autocomplete rewrite already includes **client-side** URL/identifier detection (`detectSourceFromUrl`, `parseIdentifierInput` in `citation-types.ts`). This handles the fast path — recognizing known URL patterns (IPDB, OPDB) and ISBNs before any server round-trip, enabling the guided "select parent → identify child" flow. Server-side extraction complements this as the full-featured path for external metadata resolution (Open Library, CrossRef, HTML scraping) when no existing source matches.

## API Shape

One new endpoint:

```text
POST /api/citation-sources/extract/
{ "input": "0964359219" }
```

Response (success):

```json
{
  "status": "extracted",
  "draft": {
    "name": "The Encyclopedia of Pinball, Volume 1",
    "source_type": "BOOK",
    "author": "Jeff Bueschel",
    "publisher": "Silverball Amusements",
    "isbn": "0964359219",
    "year": 1996,
    "parent": null,
    "links": []
  },
  "extractor": "isbn",
  "existing_candidates": []
}
```

Response (failure):

```json
{
  "status": "not_found",
  "reason": "isbn_not_found",
  "input_type": "isbn",
  "message": "No metadata found for this ISBN."
}
```

The `draft` object matches the shape of `CitationSourceCreateIn` so the frontend can feed it directly into the existing create flow. Nothing is persisted until the user confirms.

### Integration with the Existing Search Flow

The frontend already searches existing sources on every keystroke via `GET /api/citation-sources/search/`. Extraction is a separate, explicit step that fires only when:

1. The search returns no strong match, **and**
2. The input looks like evidence (see Input Classification below), **and**
3. The user triggers it (paste + Enter, or an explicit "Extract" action)

Extraction is never implicit-on-keystroke. Search is fast and local; extraction is slow and external.

## Input Classification

Before calling the extractor chain, the backend classifies the raw input:

| Pattern                                 | Classification                        |
| --------------------------------------- | ------------------------------------- |
| 10 or 13 digits (with optional hyphens) | `isbn`                                |
| Starts with `10.` followed by a slash   | `doi`                                 |
| Valid URL (`http://` or `https://`)     | `url`                                 |
| Anything else                           | `text` (search only, not extractable) |

Classification is deterministic regex, not heuristic. Ambiguous inputs default to `text` and are handled by search alone. The endpoint returns `not_found` with `input_type: "text"` for non-evidence inputs.

## Extractor Chain

Extractors are plain Python classes with a two-method interface:

```python
class Extractor(ABC):
    @abstractmethod
    def can_handle(self, input_type: str, raw_input: str) -> bool: ...

    @abstractmethod
    def extract(self, raw_input: str) -> CitationSourceDraft | None: ...
```

The chain runs in order. The first extractor that returns a draft wins.

### Initial Extractors

| Extractor             | Input type | External source  | Notes                                                                                                |
| --------------------- | ---------- | ---------------- | ---------------------------------------------------------------------------------------------------- |
| `ISBNExtractor`       | `isbn`     | Open Library API | Falls back to Google Books if Open Library misses                                                    |
| `DOIExtractor`        | `doi`      | CrossRef API     | Academic publications                                                                                |
| `IPDBExtractor`       | `url`      | Internal data    | Recognizes IPDB URLs, cross-references against ingested IPDB data (no live fetch — IPDB blocks bots) |
| `GenericURLExtractor` | `url`      | Remote HTML      | Extracts `<title>`, Open Graph, JSON-LD as a sparse fallback                                         |

Site-specific URL extractors (like IPDB) are ordered before the generic URL extractor so they get first crack at URLs they recognize.

### Adding a New Extractor

Add a class, register it in the chain. No plugin system, no dynamic loading, no configuration files. When the extractor count outgrows a flat list, introduce a registry. Not before.

## Failure Modes

Every failure should leave the user with a clear next step:

| Failure                                        | User sees                                                                        |
| ---------------------------------------------- | -------------------------------------------------------------------------------- |
| ISBN not found in any source                   | "No metadata found for this ISBN. Create source manually?"                       |
| DOI extraction timeout                         | "Couldn't reach CrossRef. Try again or create manually?"                         |
| URL fetch fails (404, paywall, timeout)        | "Couldn't fetch this URL. Create source manually?"                               |
| Site-specific extractor hits unexpected layout | Falls through to generic URL extractor; if that also fails, same manual fallback |

The endpoint always returns a structured response, never a 500. The `not_found` status with a `reason` code lets the frontend render appropriate messaging.

## Rate Limiting and Caching

- External API calls are rate-limited per-source (e.g., Open Library asks for max 1 req/sec).
- Successful extractions are cached by input value (e.g., cache ISBN lookups for 24 hours). Cache lives in Django's cache framework, not in the database.
- Failed lookups are cached briefly (5 minutes) to avoid hammering external APIs on retry.

## Draft Lifecycle

A draft is a transient JSON object. It is never persisted. The flow:

1. Backend returns draft in the extract response.
2. Frontend shows it in a confirmation/edit UI.
3. User confirms (possibly after editing fields).
4. Frontend POSTs to the existing `POST /api/citation-sources/` endpoint.
5. Normal CitationSource creation, with full validation.

If the user abandons the confirmation step, nothing was created. No cleanup needed.

## Deduplication

Before returning an extracted draft, the extractor checks whether the extracted metadata matches an existing source:

- ISBN exact match against `CitationSource.isbn`
- URL match against `CitationSourceLink.url`

If a match is found, the response includes `existing_candidates` so the frontend can offer "Use existing source?" instead of creating a duplicate.

## Scope and Non-Goals

**In scope:**

- The `citation/extraction/` module
- The extract endpoint and extractor chain
- ISBN, DOI, IPDB URL, and generic URL extractors
- Input classification
- Draft response shape
- Deduplication check

**Not in scope:**

- Changes to the existing search endpoint
- Changes to the CitationSource model
- Frontend implementation (separate plan)
- Bulk/batch extraction
- Background extraction or queuing
