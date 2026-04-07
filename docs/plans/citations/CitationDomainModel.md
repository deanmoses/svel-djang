# Citation Domain Model

Pinbase should distinguish between three different things:

1. **Citation source**
   The work or evidence object being cited: a book, manual, web page, video, image, observation record, museum document, interview, etc.

2. **Citation instance**
   A specific use of that source for a specific Pinbase claim or text position, including any locator such as page number, timestamp, or URL fragment.

3. **Access link**
   A way for the reader to inspect the source: canonical URL, archive URL, museum-hosted scan, repository page, uploaded asset, and so on.

These should not be collapsed into one record.

If Pinbase does collapse them, it will have trouble representing cases like:

- the same book cited on different pages
- the same manual available from both a poor internet scan and a later museum-grade scan
- the same video cited at two different timestamps
- a dead URL later replaced by an archived copy

## Examples

### A Book

- Work: _The Encyclopedia of Pinball_
- Citation source A: 1996 hardcover edition
- Citation source B: revised hardcover edition
- Citation source C: revised paperback edition
- Citation source D: revised Kindle edition
- Citation source E: revised Kindle edition, French translation

Then citation instances point into those sources:

- Citation instance 1: page 30 in citation source A
- Citation instance 2: page 83 in citation source B
- Citation instance 3: page 77 in citation source C
- Citation instance 4: location 109 in citation source D
- Citation instance 5: location 194 in citation source E

And access links are just ways to inspect a given source:

- Access link A1: archive.org scan of citation source A
- Access link B1: museum-hosted scan of citation source B
- Access link D1: Kindle Store page for citation source D

#### Self-Referential Source Hierarchy

The examples above use a flat list of citation sources plus a separate "Work" grouping. A cleaner model is to make CitationSource self-referential: a source can have a `parent` source, just as Location has a `parent` location. A root source (no parent) is the abstract work; children are progressively more specific published forms.

##### Industry precedent

Every major bibliographic system has grappled with how many levels to put between "the abstract intellectual work" and "a specific citation pointing to page 30":

- **FRBR** (library science) defined four levels: Work → Expression → Manifestation → Item. The Expression/Manifestation boundary confused even librarians. After years of low adoption, IFLA consolidated it into the simpler LRM.
- **Wikidata** studied FRBR and collapsed it to two levels: Work and Edition. An edition links to its work via `edition or translation of` (P629). When only one edition exists, a single item serves both roles.
- **Schema.org** similarly uses just CreativeWork + `workExample`, deliberately rejecting FRBR's depth.
- **BibTeX and Zotero/CSL** are flat — one record per source, no Work-level entity. Both hit duplicate/reuse problems at scale: no way to express "these five entries are editions of the same book."

The consensus: two levels is the sweet spot. Four was too rigid; one was too flat. A self-referential parent FK gives us two levels by default while allowing more when the data actually needs it — without forcing it.

##### The Book example, reworked

With a self-referential CitationSource, the book example becomes:

```text
The Encyclopedia of Pinball
├── 1996 Edition 1
└── 1999 Edition 2
   └── French translation
         ├── Edition 2 hardcover version, French translation
         ├── Edition 2 paperback version, French translation
         └── Edition 2 Kindle version, French translation
```

Citation instances point to whichever level the editor knows:

- Citation instance 1: page 30 in "1996 hardcover edition"
- Citation instance 2: location 194 in "French translation"
- Citation instance 3: page 42 in "The Encyclopedia of Pinball" (editor doesn't know which edition)

Access links attach to the appropriate level:

- Access link: archive.org scan → attached to "1996 hardcover edition"
- Access link: Kindle Store page → attached to "revised Kindle edition"
- Access link: publisher's landing page → attached to "The Encyclopedia of Pinball" (the root, because it covers all editions)

##### Simple sources

Most pinball citation sources — a flyer, a web page, a museum observation, a YouTube video — are just root sources with no children. The hierarchy adds no overhead for the common case.

##### Citing a non-leaf

A citation instance can point to any level, not just a leaf. This matters because a source that is a leaf today may gain children later. If someone cites "The Encyclopedia of Pinball" because they only know one edition, and later someone adds edition records as children, the original citation remains valid — it just means "I cited this work but didn't specify which edition."

The soft convention is: **prefer the most specific source you know.** If you know the edition, cite the edition. If you only know the work, cite the work.

##### Autocomplete UX

This hierarchy directly supports the editorial workflow:

1. Editor types "enc..." → autocomplete shows "The Encyclopedia of Pinball" (root source)
2. Editor selects it → if it has children, a second step shows editions
3. If no children (a flyer, a web page), the editor is done — cite the root directly

This avoids both failure modes: showing a wall of near-identical edition permutations in autocomplete (too noisy), and forcing the editor to navigate a mandatory Work → Edition flow when most sources only have one form (too ceremonial).

### A Magazine Article

A print magazine article is usually its own citation source, nested under the issue that published it, which in turn can be nested under the publication.

Example: a Roger C. Sharpe review article in _Play Meter_, issue `1978 August 15 - Vol 4 Num 15`, archived by the International Arcade Museum Library. The archive page for [page 35](https://elibrary.arcade-museum.com/Play-Meter/1978-August-15/35) shows the byline `By Roger C. Sharpe` and includes his reviews of Recel's `Fair Fight` and Gottlieb's `Hit the Deck` across pages 35-36.

Model:

- Root source: `Play Meter`
- Child source: `1978 August 15 - Vol 4 Num 15`
- Citation source: `Roger C. Sharpe review article covering Fair Fight and Hit the Deck`
- Type: `magazine article`
- Publication: `Play Meter`
- Author: `Roger C. Sharpe`
- Published: `1978-08-15`

Access links:

- International Arcade Museum Library page 35
- International Arcade Museum Library page 36
- later, potentially, a full-issue PDF or another archive copy

Citation instances:

- Claim: Sharpe described Recel's `Fair Fight` as notable for allowing multiple extra balls in a multi-player game
  - source: `Roger C. Sharpe review article covering Fair Fight and Hit the Deck`
  - locator: `page 35, Fair Fight section`
- Claim: Sharpe called Gottlieb's `Hit the Deck` "the last single-player electro-mechanical machine from this manufacturer"
  - source: same article
  - locator: `page 36, Hit the Deck section`

The important point is that:

- the article or column is the citation source
- the issue is a useful parent source for grouping and bibliographic context
- page numbers and section names belong on the citation instance
- page scans or issue PDFs are access links, not separate citation sources

### A Website

Example: Pinball Magazine's web article [Report: EAG Expo 2025](https://www.pinball-magazine.com/?p=6033). The page is dated January 17, 2025, attributed to `Editor`, and the article text explicitly says "Pinball Magazine Editor Jonathan Joosten reports on this year's edition."

Model:

- Root source: `Pinball Magazine`
- Citation source: `Report: EAG Expo 2025`
- Type: `magazine article`
- Publication: `Pinball Magazine`
- Author: `Jonathan Joosten`
- Published: `2025-01-17`

Access links:

- the Pinball Magazine article URL
- later, potentially, an archived snapshot URL

Citation instances:

- Claim: EAG Expo is the first coin-op industry tradeshow of the year in London
  - source: `Report: EAG Expo 2025`
  - locator: opening paragraphs
- Claim: Stern Pinball was represented by Seth Davis, Gary Stern, John Buscaglia, Doug Skor, and Lloyd Dortand
  - source: same article
  - locator: paragraph beginning `Stern Pinball usually sends a heavy delegation`
- Claim: Retro Arcade Specialists had games including `Labyrinth`, `The Blues Brothers`, `Hot Wheels`, and `Houdini`
  - source: same article
  - locator: paragraph beginning `Following the interview, I headed to the stand of Retro Arcade Specialists`

The important point is that:

- the article is the citation source, not just the magazine as a whole
- the publication can still exist as a parent source for grouping
- paragraph references or section headings are the locator on the citation instance
- the live URL and any archive copy are access links, not separate citation sources

### An Interview

### A Manufacturer Press Flyer

A manufacturer flyer is usually one citation source, even if it has multiple sides or multiple scans.

Example: Williams _Medieval Madness_ flyer. The [IPDB Medieval Madness page](https://www.ipdb.org/machine.cgi?id=4032) includes both "Flyer, Front" and "Flyer, Back", and its listed machine dimensions are explicitly from the manufacturer's flyer.

Model:

- Citation source: `Williams Medieval Madness manufacturer flyer`
- Type: `flyer / document`
- Publisher / creator: `Williams`
- Year: `1997`
- Language: `English`

Access links:

- IPDB flyer front image
- IPDB flyer back image
- later, potentially, a museum-hosted reference scan PDF of the same flyer

Citation instances:

- Claim: marketing slogan or sales copy from the front
  - source: `Williams Medieval Madness manufacturer flyer`
  - locator: `front`
- Claim: height `75 inches`
  - source: same flyer
  - locator: `back, specifications`
- Claim: weight `355 lbs`
  - source: same flyer
  - locator: `back, specifications`

The important point is that:

- the flyer is the citation source
- `front`, `back`, and `specifications` are locators on citation instances
- front and back scans are access links, not separate citation sources, unless they turn out to be materially different flyer versions

### A Pinball Machine Manual

Pinball manuals are often a small source family rather than one flat source. A game may have:

- an operator's handbook
- an operations manual
- a schematic manual
- language-specific instruction booklets
- later amendments or addenda

Example: Midway's _The Addams Family_. The [IPDB Addams Family page](https://www.ipdb.org/machine.cgi?gid=20) lists, among other documents:

- `Operator's Handbook` (January 1991)
- `Operations Manual` (January 1992, includes schematics)
- `Instructions Manual` (French, undated)
- `WPC Schematic Manual` (January 1992)

The cleanest model is usually a source family with child sources:

```text
The Addams Family documentation
├── Operator's Handbook (January 1991)
├── Operations Manual (January 1992)
├── Instructions Manual
      └── Instructions Manual, French
└── WPC Schematic Manual (January 1992)
```

That means:

- the root source groups the documentation set
- the individual manuals are the citation sources contributors usually cite

Citation instances then point to the specific manual actually consulted:

- Citation instance 1: setup instruction from `Operator's Handbook (January 1991)`, locator `page 12`
- Citation instance 2: coil or switch detail from `Operations Manual (January 1992)`, locator `section 3`
- Citation instance 3: wiring detail from `WPC Schematic Manual (January 1992)`, locator `page 4-22`
- Citation instance 4: translated player instruction from `Instructions Manual, French`, locator `page 2`

Access links are just ways to inspect those sources:

- IPDB PDF for `Operations Manual (January 1992)`
- later, a museum-hosted higher-quality scan of that same manual
- later, an OCR-corrected text view derived from the same manual

The important point is that:

- different manuals for the same machine are usually different citation sources, not just locators within one source
- a better scan of the same manual is usually a new access link, not a new citation source
- page numbers, section references, and schematic-sheet references belong on the citation instance

## Field Analysis

Working through concrete fields to discover what's shared, what's type-specific, and what lives on child sources vs root sources.

### Book: _The Encyclopedia of Pinball_

**Root source (the work):**

| Field     | Value                       |
| --------- | --------------------------- |
| title     | The Encyclopedia of Pinball |
| type      | book                        |
| author    | Richard Bueschel            |
| publisher | Silverball Amusements       |
| parent    | null                        |

**Child source (an edition):**

| Field    | Value                         |
| -------- | ----------------------------- |
| title    | Edition 1                     |
| type     | book                          |
| year     | 1996                          |
| format   | hardcover                     |
| language | English                       |
| parent   | → The Encyclopedia of Pinball |

**Deeper child (a translation of an edition):**

| Field    | Value              |
| -------- | ------------------ |
| title    | French translation |
| type     | book               |
| language | French             |
| parent   | → Edition 2        |

Observations:

- **author and publisher live on the root**, not repeated on every child. A child inherits them from its parent chain.
- **year, format, and language are differentiators** — they're the reason a child exists as a separate source.
- **title on a child is relative to its parent.** The full display name is assembled by walking the parent chain: "The Encyclopedia of Pinball → Edition 2 → French translation → Kindle version."
- **ISBN could go on the format-level child** (the specific hardcover or Kindle edition), since each format has its own ISBN.

### Manual: _The Addams Family_ documentation

**Root source (the documentation family):**

| Field     | Value                           |
| --------- | ------------------------------- |
| title     | The Addams Family documentation |
| type      | manual                          |
| publisher | Midway                          |
| parent    | null                            |

**Child source (a specific manual):**

| Field    | Value               |
| -------- | ------------------- |
| title    | Operations Manual   |
| type     | manual              |
| year     | 1992                |
| date     | January 1992        |
| language | English             |
| parent   | → TAF documentation |

**Child source (a translated manual):**

| Field    | Value                 |
| -------- | --------------------- |
| title    | French                |
| type     | manual                |
| language | French                |
| parent   | → Instructions Manual |

### Pattern emerging

The same small set of fields covers both books and manuals:

| Field     | Book root | Book child | Manual root | Manual child |
| --------- | --------- | ---------- | ----------- | ------------ |
| title     | yes       | yes        | yes         | yes          |
| type      | yes       | yes        | yes         | yes          |
| author    | yes       | rare       | no          | no           |
| publisher | yes       | no         | yes         | no           |
| year      | no        | yes        | no          | yes          |
| date      | no        | rare       | no          | yes          |
| format    | no        | yes        | no          | no           |
| language  | no        | yes        | no          | yes          |
| isbn      | no        | yes        | no          | no           |

Most fields are optional, most rows are sparse. The question is whether this pattern holds across other source types (web pages, videos, observations, flyers) or whether those types need fields that don't fit this set.

### Website: Pinball Magazine article

Two levels: publication → article. No issue-level grouping needed — web articles don't belong to numbered issues.

**Root source (the publication):**

| Field  | Value            |
| ------ | ---------------- |
| title  | Pinball Magazine |
| type   | website          |
| parent | null             |

**Child source (the article):**

| Field  | Value                 |
| ------ | --------------------- |
| title  | Report: EAG Expo 2025 |
| type   | website               |
| author | Jonathan Joosten      |
| date   | 2025-01-17            |
| year   | 2025                  |
| parent | → Pinball Magazine    |

Observations:

- **No new fields needed.** A web article uses title, type, author, date, year, and parent — all fields we already have from books and magazines.
- **URL is not a source field — it's an access link.** The article _is_ the source; the URL is how you get to it. If the site goes down and an archive.org copy exists, the source is unchanged — only the access links change.
- **No volume/issue/pages.** Web articles don't have these. The fields are simply unused, which is fine — the model is sparse by design.
- **The type could be `website` or `magazine`.** Pinball Magazine publishes both print and web. The type on the source distinguishes the form. A print issue and a web article from the same publication are siblings with different types under the same root.

### Magazine article: Roger C. Sharpe in _Play Meter_

Three levels: publication → issue → article.

**Root source (the publication):**

| Field  | Value      |
| ------ | ---------- |
| title  | Play Meter |
| type   | magazine   |
| parent | null       |

**Child source (the issue):**

| Field  | Value                         |
| ------ | ----------------------------- |
| title  | 1978 August 15 - Vol 4 Num 15 |
| type   | magazine                      |
| date   | 1978-08-15                    |
| year   | 1978                          |
| volume | 4                             |
| issue  | 15                            |
| parent | → Play Meter                  |

**Child source (the article):**

| Field  | Value                                                       |
| ------ | ----------------------------------------------------------- |
| title  | Roger C. Sharpe review covering Fair Fight and Hit the Deck |
| type   | magazine                                                    |
| author | Roger C. Sharpe                                             |
| pages  | 35-36                                                       |
| parent | → 1978 August 15 - Vol 4 Num 15                             |

New fields that weren't needed for books or manuals:

- **volume** and **issue** — structured identifiers for periodicals. Could be part of the title string instead, but structured fields enable better display formatting ("Vol. 4, No. 15") and search.
- **pages** — the page range of the article within the issue. This is a property of the source itself ("this article runs pages 35-36"), distinct from a locator on a citation instance ("I'm citing the Fair Fight section on page 35").

### Updated field inventory

| Field     | Book | Manual | Magazine | Flyer |
| --------- | ---- | ------ | -------- | ----- |
| title     | yes  | yes    | yes      | yes   |
| type      | yes  | yes    | yes      | yes   |
| author    | yes  | no     | yes      | no    |
| publisher | yes  | yes    | no       | yes   |
| year      | yes  | yes    | yes      | yes   |
| date      | rare | yes    | yes      | no    |
| format    | yes  | no     | no       | no    |
| language  | yes  | yes    | no       | yes   |
| isbn      | yes  | no     | no       | no    |
| volume    | no   | no     | yes      | no    |
| issue     | no   | no     | yes      | no    |
| pages     | no   | no     | yes      | no    |

The field set is growing but staying manageable. Each new source type adds one or two fields; no type uses more than about half the total set
