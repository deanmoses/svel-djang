# Citations

How Pinbase should handle citations for article-like text and factual claims, based on the business need for verifiability and the UX failures of existing wiki systems.

## Background and Business Case

Pinbase is trying to build the most comprehensive and trusted body of pinball knowledge in the world. The definitive online encyclopedia of pinball.

As such, Pinbase is trying to solve a problem that the major pinball databases do not solve well: not just storing facts, but preserving where those facts came from.

Current pinball stores of knowledge don't solve this. IPDB has a huge problem of "who says?". Since on IPDB the text isn't attributed or referenced, it's very hard to tell actual fact from hearsay nonsense, which the pinball world is full of. With Wikipedia, at least you can take a look at edit history and figure out where a piece of text came from. But with IPDB there's no way to tell anything.

When a page mixes careful research, community memory, primary-source facts, and hearsay, but the reader cannot tell which is which, the whole page becomes harder to trust.

This matters for Pinbase more than it would for a standard hobby site.

- The project aims to be an encyclopedia. It carries a museum brand. Claims have a higher expectation of care than an entertainment site.
- Pinball history is full of lore, retellings, and half-remembered anecdotes. Provenance is not a nice-to-have; it is the mechanism that separates durable history from repeated rumor.
- The long-term value of the site is compounding knowledge. A fact that is not tied to evidence is expensive to maintain because every future editor has to rediscover the same validation work.
- The contributor base will include knowledgeable enthusiasts, collectors, museum staff, and other people with access to primary materials. Pinbase should make that evidence legible rather than flattening it into unattributed prose.

The business case for citations is therefore straightforward.

### 1. Citations make pages more trustworthy

The immediate product value is reader trust. A statement backed by a flyer, manual, interview, museum document, or documented observation is qualitatively different from an unattributed claim. Even when a reader does not click through, the presence of a visible citation structure signals that facts are contestable and reviewable rather than merely asserted.

### 2. Citations lower the maintenance cost of accuracy

When a contributor, curator, or future editor questions a statement, the best-case outcome is not an argument. It is a quick verification loop:

- read the claim
- inspect the source
- confirm or correct it

That is one of Wikipedia's great operating ideas. Pinbase needs the same basic loop even if its evidence standards differ. Without citations, every disputed statement becomes expensive because the editor must first reconstruct provenance before they can evaluate truth.

### 3. Citations improve contributor behavior

The existence of a citation surface changes how people write. It encourages narrower, more defensible claims, reduces overconfident synthesis, and makes contributors think about whether a statement is supported, observed, or inferred. That is especially valuable in a domain where community folklore spreads easily.

### 4. Citations let Pinbase support primary sources and original research honestly

Pinbase is not Wikipedia and should not pretend to be. The project is likely to accept classes of evidence that Wikipedia rejects or treats awkwardly:

- primary-source documents such as flyers, manuals, and operator materials
- museum-owned documents and internal records
- uploaded photographs taken by contributors
- documented in-person observation
- interviews and correspondence

Those are legitimate inputs for this product, but only if they are made explicit. "Original research" without attribution is just hidden editorial authority. Pinbase's opening is not "trust us instead of Wikipedia." It is "show the evidence, including kinds of evidence that Wikipedia is structurally bad at handling."

### 5. Citations create institutional memory

At small scale, knowledge systems often rely on a few people who "just know" why a statement is on a page. That does not survive turnover. Citations externalize memory. They allow a future editor to understand not only what the page says, but what source base the page was built from.

### Citation vs. Edit Note

Pinbase already has an "Edit note" concept. That should remain, but it is not a substitute for citations.

- A citation is public evidence for the claim.
- An edit note is workflow metadata explaining what changed or why the editor made the edit.

Those are different jobs. "Fixed wording" is a fine edit note and a useless citation. "Williams flyer, 1993" is a useful citation and an incomplete edit note. Pinbase should preserve both concepts rather than collapsing them together.

## Research and Comparable Systems

The relevant question is not simply "who has citations?" It is "how do comparable systems make evidence attach to prose, and what friction does that create for contributors?"

### Wikipedia / MediaWiki

Wikipedia is the canonical example because its citation system is deeply tied to its quality model. The core workflow is sound: a skeptical reader or editor should be able to inspect a footnote, check the source, and verify the statement. That principle is exactly right for Pinbase.

The problem is the authoring model.

Wikipedia's traditional citation flow requires editors to insert inline markup into the prose using `<ref>` tags, citation templates, named references, and other wikitext conventions. VisualEditor improves the experience by adding dialogs and forms, but the underlying model is still inline footnotes embedded in the article body. That creates several kinds of friction:

- prose and evidence are authored together rather than separately
- casual edits become template edits
- reusing a source requires editor-specific knowledge
- moving or rewriting text can break citation placement
- the article source becomes harder to read as prose

Wikipedia accepts that cost because verifiability is central to the project and because its editor culture is already willing to tolerate procedural complexity. But the museum director's instinct is right: the citation syntax and editing flow absolutely shrink the pool of people willing to contribute.

Pinbase should copy Wikipedia's commitment to verifiability and reject Wikipedia's requirement that contributors hand-author citation markup in the prose.

### Fandom and other MediaWiki-derived wikis

Hosted wiki systems that inherit MediaWiki conventions generally inherit the same citation tradeoff: powerful footnotes, high markup friction, and weak suitability for casual contributors. Many such communities simply avoid rigorous citation practice except in their most quality-sensitive spaces, because the work of adding and maintaining citations is disproportionately annoying relative to the value contributors perceive.

That is a warning for Pinbase. If citations feel like "Wikipedia homework," most contributors will skip them, and the product will end up with either sparse sourcing or a culture gap between a small number of power editors and everyone else.

### MusicBrainz and Discogs

MusicBrainz and Discogs are useful counterpoints because they care deeply about database quality but do not primarily rely on article-like inline footnotes.

Their dominant pattern is closer to edit justification than public citation:

- editors explain changes in submission notes or edit notes
- discussion and review happen around edits
- the systems preserve some rationale and accountability

This works reasonably well for structured catalog data, where the main question is often "should this field value change?" rather than "how should a long-form narrative paragraph be sourced?" The weakness is reader verifiability. An outside reader of the final page often cannot see evidence as directly as they can on Wikipedia.

The lesson for Pinbase is that edit notes are necessary but insufficient. They help with workflow and review, but they do not by themselves answer the reader-facing "who says?" question.

### Wikimedia Commons and media-heavy knowledge systems

Wikimedia Commons, museum collection systems, and observation platforms such as iNaturalist are useful because they handle evidence objects that are not just books and URLs. They distinguish between concepts like:

- source
- author / photographer
- license
- observed by
- uploaded by

That is important for Pinbase because some of its most valuable evidence will be images and observations, not published secondary sources. A photo taken by a trusted contributor at The Flip is not "a citation" in the same shape as a URL, but it is still evidence and should be representable as such.

The lesson here is that Pinbase should use a broader evidence model than generic web citations.

## What the Research Implies

The comparables point to three practical conclusions.

### 1. Verifiability is worth copying

Wikipedia is right that a knowledge system needs a fast loop from claim to evidence. Pinbase should preserve that principle.

### 2. Inline citation markup is not worth copying

Wikipedia's in-text footnote model is powerful but editor-hostile. It asks contributors to think about prose, source formatting, and footnote mechanics all at once. Pinbase should not require manual citation syntax in the body text.

### 3. Pinbase needs something between "edit note" and "full footnote template system"

If Pinbase does only edit notes, it will not solve the public-trust problem. If it clones Wikipedia's inline ref model, it will solve that problem at too high a contributor cost. The product opportunity is to separate writing from citation authoring while still producing reader-visible references.

## Proposal for Pinbase

Pinbase should adopt a `write first, cite second` citation model.

The core idea is simple:

- contributors write normal prose in the editor
- citations are attached through structured UI, not typed as inline markup
- the system renders footnote markers and source lists automatically in read view

This preserves verifiability while removing the need for contributors to author or maintain citation syntax manually.

## Product Principles

### 1. Keep prose and citation markup separate

The editing surface for the article body should remain readable prose. Contributors should not have to interleave `<ref>` tags, templates, or custom syntax with the article text.

### 2. Make the common case easy

Most edits are not complex historiographic essays. Many are simple cases:

- one paragraph rewritten from one source
- a new fact added from a flyer or manual
- a museum staff member documenting an observation

The default flow should make those cases easy with one or two source attachments, not a miniature scholarly apparatus.

### 3. Support stronger granularity only when needed

Not every page needs sentence-level references. Pinbase should support progressively finer attribution:

- article-level
- paragraph-level
- selected-text, later if justified

The product should start at the simplest useful level and only increase precision where it materially helps.

### 4. Treat evidence types as first-class

Pinbase should not force every citation into a URL field. The system should explicitly support evidence types that make sense for this domain.

Recommended source types:

- web page / URL
- book or magazine
- flyer / manual / document
- uploaded photo
- museum record
- interview / correspondence
- in-person observation
- other

### 5. Preserve compatibility with the claims/provenance model

Pinbase already has a claims-based provenance architecture. Citations should fit that model rather than inventing a parallel truth system. The citation layer should explain and support claims, not replace claim attribution.

## UX Recommendation

### Recommended editing flow

For article-like text, the editor should have two distinct areas:

1. **Article body**
   The contributor writes normal Markdown prose with no citation markup required.

2. **Sources**
   A structured section below the editor where the contributor attaches evidence to the article or to specific parts of it.

The default interaction should be:

- write or edit prose
- click `Add source`
- choose source type
- fill in citation details
- choose what the source applies to

The "what does this source apply to?" options should start simple:

- entire article
- a paragraph

Later, if justified, Pinbase can support:

- selected text

### Why paragraph-level is the right starting point

Paragraph-level citations are the best initial tradeoff.

- More precise than one citation for an entire article
- Much simpler than sentence-level inline footnotes
- Easy to explain to first-time editors
- Robust when prose is lightly edited

This is materially better than a single citation box for the entire edit, but far less intimidating than Wikipedia's inline ref model.

### The role of Edit Note

The existing bottom-of-form `Edit note` should remain. It should sit alongside, not instead of, citations.

The bottom of an article edit form should therefore conceptually have:

- `Sources`
- `Edit note`

The contributor should understand:

- `Sources`: what evidence supports the new or changed content
- `Edit note`: what changed in this save

### Advanced mode for complex edits

The UI should not dump per-field or per-paragraph citation controls on every editor by default. Instead:

- default to a simple `Add source` flow
- let one source apply to multiple paragraphs
- reveal more detailed controls only when the contributor chooses them

This avoids doubling the apparent size of the form while still allowing stronger sourcing where needed.

## Read-Side Presentation

On the published page, Pinbase should render citations as ordinary footnote markers and a source list, but those markers should be generated by the system rather than authored by the contributor.

Recommended read-side presentation:

- small superscript reference markers attached to paragraphs or blocks
- a `Sources` or `References` section at the bottom of the article
- each reference entry showing the evidence type and its details
- where applicable, links to uploaded media, documents, or URLs

This gives readers the familiar "check the footnote" affordance without importing Wikipedia's editing pain.

## Data and Model Direction

The exact implementation can vary, but the product model should distinguish among three things:

1. **The prose**
   The article or description text itself

2. **The claim attribution**
   Who asserted the content in Pinbase's provenance system

3. **The evidence objects**
   The citations or source attachments that support all or part of that prose

That separation matters.

- A user claim says who entered or asserted the text in Pinbase.
- A citation says what outside evidence, primary material, or documented observation supports it.

For descriptions and long-form article text, a likely direction is:

- keep the text as a claims-backed field
- attach one or more citation records to that field's content
- allow each citation record to target the whole text or a specific block

Pinbase should not overload the existing single-string claim `citation` field to carry the entire future article-citation system. That field is useful for simple attribution and should remain useful. But article citations will likely need structured data:

- type
- display text
- URL or linked media/document
- optional author / photographer / observer
- optional date
- optional page number or locator
- target range or block

## Rollout Plan

The safest approach is phased.

### Phase 1: Simple structured citations for article edits

- Add a `Sources` section to article-like editors
- Support one or more structured source entries
- Allow article-level or paragraph-level attachment
- Render references automatically in read view
- Keep `Edit note` unchanged

This phase solves the primary product problem: visible evidence without inline citation markup.

### Phase 2: Better evidence integration

- Reuse uploaded photos and museum-owned documents as citation targets
- Support richer source-type-specific forms
- Improve source reuse across multiple paragraphs or pages

This phase makes Pinbase's evidence model more domain-native.

### Phase 3: Finer-grained citation targeting if needed

- Selected-text attachment
- Better paragraph reflow handling
- More advanced editing affordances

This phase should only happen if real usage shows paragraph-level citations are insufficient.

## Things Pinbase Should Explicitly Avoid

- requiring contributors to type footnote syntax by hand
- requiring every field on a page to have its own citation input visible all the time
- treating edit notes as if they were equivalent to citations
- forcing all evidence into a URL-shaped model
- building sentence-level precision before the product has proven it needs that complexity

## Recommendation

Pinbase should adopt the principle behind Wikipedia citations and reject the mechanism.

The principle to copy is:

- every meaningful factual statement should be verifiable from visible evidence

The mechanism to reject is:

- inline hand-authored citation markup embedded directly in the prose

The right Pinbase system is a structured citation UI that lets contributors write prose normally, then attach evidence to the article or paragraph through forms. The site should render ordinary-looking footnotes for readers, but the contributor should never have to type a footnote language to get there.

That approach is the best fit for Pinbase's actual opportunity:

- stronger trust than IPDB
- less procedural friction than Wikipedia
- better support for primary sources, photos, and museum documentation
- clean alignment with the existing provenance model
