# Citation Sharing: Shared vs. Independent Citations

How Pinbase should think about reusable citation sources versus page-local or claim-local citation creation.

## The Question

When multiple claims cite "the same source" -- like two separate articles referencing _The Encyclopedia of Pinball_ -- should Pinbase treat those citations as:

- completely independent citations created separately each time, or
- shared citation records reused across pages, claims, and contributors

This is a foundational product decision. It determines:

- how much work contributors repeat
- how consistent citations become over time
- how much editorial coordination the system requires
- how painful it is to fix metadata errors later
- whether citations become durable infrastructure or remain page-by-page prose accessories

## The Two Extremes

### Model A: Fully independent citations

Every citation is created locally where it is used. If five pages cite the same book, Pinbase stores five unrelated citation records.

Benefits:

- easiest mental model
- no shared-record governance
- no need to deduplicate before saving
- low risk that editing one citation accidentally changes many pages

Costs:

- repeated data entry
- inconsistent metadata for the same source
- hard to find every use of a source
- hard to improve source metadata globally
- hard to upgrade source access over time

This is roughly the failure mode of many wiki systems: citations work locally, but the system never becomes a reusable source graph.

### Model B: Fully shared citations

Every citation must reuse an existing canonical shared record if one exists. Contributors are expected to search, match, and cite from a central source database.

Benefits:

- less duplicate metadata
- stronger consistency
- global visibility into source reuse
- corrections and enrichments can benefit many pages

Costs:

- contributors must search before citing
- duplicate detection becomes product-critical
- messy edge cases become blocking
- editing shared records becomes socially and operationally sensitive
- contributors may feel they are editing a bibliography system, not writing about pinball

This is where centralized systems become dangerous. The system starts helping quality, but can easily start taxing contribution.

## Research

The real question is not which model sounds cleaner in the abstract. It is which tradeoff comparable systems have actually made, and what problems those choices create.

### Wikipedia does not have shared citations in the Pinbase sense

Wikipedia does not have a general system where citations resolve to reusable, normalized shared source records across the encyclopedia.

In MediaWiki today, citations are fundamentally page-local. They are built around inline `<ref>` tags on the page being edited, with local templates layered on top. See [Extension:Cite](https://www.mediawiki.org/wiki/Extension:Cite). That means:

- a citation lives where it is typed
- reuse is mostly manual
- the same source can be represented differently on many pages

Wikimedia's [Shared Citations proposal](https://meta.wikimedia.org/wiki/WikiCite/Shared_Citations) exists precisely because this limitation is real and costly.

### Reasons Wikimedia has not centralized citations

#### 1. It's hard to retrofit

Wikipedia has 20+ years of citations embedded in pages. The [Shared Citations proposal](https://meta.wikimedia.org/wiki/WikiCite/Shared_Citations) cites the difficulty of mapping those embedded page-local citations to corresponding items in Wikidata.

The lesson for us: if we're going to have shared sources, do it from the beginning to avoid the retrofit cost.

#### 2. Scale and volume

The [Shared Citations proposal](https://meta.wikimedia.org/wiki/WikiCite/Shared_Citations) explicitly notes the undesirability of storing the full mass of individual URLs and articles as centralized records. At Wikimedia scale, the number of possible sources is enormous.

The lesson for us: we have a far smaller domain with a narrower source universe. This deserves more analysis but I wouldn't consider it a showstopper for us right now.

#### 3. Scope and ontology ambiguity

The [Shared Citations proposal](https://meta.wikimedia.org/wiki/WikiCite/Shared_Citations) raises questions about what should count as a shared citation entity and what "completeness" would mean for a central repository. In other words: what exactly is the thing being centralized?

Example:

- Book: The Encyclopedia of Pinball
- Edition A: 1996 hardcover
- Edition B: later revised edition
- Citation 1: page 30 in Edition A
- Citation 2: page 83 in Edition B hardcover
- Citation 3: page 77 in Edition B paperback
- Citation 4: location 109 in Edition B Kindle

What is the shared citation source record here? Possible answers:

- one record for the work
- one record per edition

The lesson for us: we need to decide what these shared sources are, what information belongs on it, and what stays local to a citation site. If we can't come up with convincing answers, then we can't centralize the sources.

#### 4. Governance and change propagation

Once a shared citation record is reused widely, editing it has broader consequences. Wikimedia explicitly calls out the need for tooling to monitor how changes propagate across pages and wikis.

This reason applies to Pinbase:

- **yes**

Pinbase has a single editorial community rather than many wikis, which helps a lot. But shared records still create governance questions: who edits them, how changes are reviewed, and how editors understand downstream impact.

#### 5. Local editorial and style independence

Wikimedia is not one editorial community. Different projects want different display conventions, sourcing norms, and local control. Shared citation infrastructure therefore has political and editorial consequences, not just technical ones.

This reason applies to Pinbase:

- **much less**

Pinbase is one product with one design system and one core editorial culture. This is one of the strongest reasons Pinbase can do something Wikimedia struggles to do.

#### 6. Workflow friction

Wikimedia's tool history shows that citation entry friction is a serious concern. [Citoid](https://wikitech.wikimedia.org/wiki/Citoid) exists largely to reduce the burden of reference creation by pulling metadata from an identifier or URL.

The lesson is straightforward: if citation authoring feels like bibliography maintenance, contributors will avoid it.

This reason applies to Pinbase:

- **strongly**

This may be the single most important reason for Pinbase to avoid a rigid central-bibliography workflow.

### What the Wikipedia case means for Pinbase

Wikipedia's situation does not argue against shared citation sources in principle.

It argues for three narrower conclusions:

- introducing shared citations earlier avoids the mapping difficulties that Wikimedia explicitly calls out
- shared records create real governance and product-surface obligations
- citation reuse must assist editing, not burden it

That means Pinbase should learn from both halves of the Wikimedia story:

- the current page-local model creates duplication and weak reuse
- the proposed fix is hard because centralization introduces scale, governance, and workflow problems of its own

### Human behavior still matters

Even outside Wikimedia specifically, contributors do not behave like librarians during ordinary editing. They optimize for finishing the edit in front of them.

That means:

- if reuse is easy, they will often reuse
- if reuse is annoying, they will quick-create or skip citing
- if quick-create is hard, they may skip citing entirely

This is the key behavioral constraint. The product cannot assume that contributors will tolerate a bibliographic workflow just because the shared-data story is elegant.

## What the Research Implies

The research does not support either extreme.

It argues against fully independent citations because that produces duplication, inconsistency, and poor long-term maintainability.

It also argues against fully shared citations because that turns citation authoring into a normalization task and creates unnecessary workflow drag.

The more defensible product stance is:

- source reuse should be possible and encouraged
- source reuse should not be mandatory to save an edit
- contributors should be able to quick-create when matching is unclear
- duplicates should be acceptable in the short term
- cleanup and merging should be possible later

This is the product shape that respects both editorial quality and actual human behavior.

## Contributor Workflow Implications

If Pinbase chooses this middle path, the workflow should look like this:

1. Search for an existing citation source.
2. If a good match exists, reuse it.
3. If not, quick-create a new source without leaving the editing flow.
4. Save the citation use without requiring perfect normalization.

The important rule is:

- **Reuse should be easy.**
- **Quick-create should also be easy.**

If quick-create is hard, contributors will avoid citing.

If reuse is hard, Pinbase will accumulate avoidable duplicates.

The system therefore needs to tolerate some duplicates as the price of keeping citation authoring fluid.

## Governance Implications

If Pinbase supports reusable citation sources, it should keep the shared layer narrow enough that editing it remains safe.

Good candidates for shared records are things like:

- title
- author or creator
- publication details
- evidence type
- stable identifiers
- reusable access information

Things that are specific to a particular use should not be treated as part of the shared-record problem. Those belong elsewhere in the citation model.

See [CitationDomainModel.md](CitationDomainModel.md) for that separation.

## What Pinbase Should Avoid

- treating every citation as entirely page-local forever
- forcing contributors to resolve duplicates before they can save
- turning ordinary citation authoring into a library-catalog workflow
- assuming perfect deduplication is required for v1
- making shared records so broad that editing them becomes high-risk

## Recommendation

Pinbase should not choose between "fully shared" and "fully independent" citations.

It should adopt a hybrid stance:

- support reusable shared citation sources
- allow independent citation creation when reuse is unclear or inconvenient
- treat duplicate detection and source merging as an ongoing editorial improvement process, not a prerequisite for saving

The governing product rule should be:

**Centralization should assist citation reuse, not gate citation authoring.**

That gives Pinbase:

- better contributor ergonomics than a strict central bibliography workflow
- more long-term consistency than page-local wiki citations
- a realistic path to improved metadata, preservation, and source-quality upgrades over time

## Open Questions

- Should duplicates be merged manually, automatically, or both?
- How aggressively should the editor nudge contributors toward reusing an existing source before quick-creating a new one?
- Should some source types be more aggressively deduplicated than others?
- What editorial tools are needed to review and merge near-duplicate shared sources later?

## References

- [MediaWiki Extension:Cite](https://www.mediawiki.org/wiki/Extension:Cite)
- [WikiCite/Shared Citations](https://meta.wikimedia.org/wiki/WikiCite/Shared_Citations)
- [Citoid](https://wikitech.wikimedia.org/wiki/Citoid)
