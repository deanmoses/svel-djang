# Citations - Prior Art

Relevant systems and design lessons for how Pinbase should handle citations.

This document focuses on comparable products and what they imply. See:

- [Citations.md](Citations.md) for the root overview and product direction
- [CitationsBusinessCase.md](CitationsBusinessCase.md) for the business case
- [CitationsDesign.md](CitationsDesign.md) for the design and architecture

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
