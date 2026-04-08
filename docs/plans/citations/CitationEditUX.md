# Citation Edit UX

Research on citation editing UX, focused first on Wikipedia / MediaWiki's
`Citoid` flow.

## Citoid

Citoid is the main built-in automatic citation tool in Wikimedia editing. It is deployed on all VisualEditor-enabled Wikimedia wikis, and its citation autofill is available in VisualEditor and the 2017 wikitext editor.

### What Citoid Is

Citoid is an
auto-filled citation generator.

1. the editor accepts a source-like input
2. Citoid tries to resolve it into structured bibliographic metadata
3. local template maps decide how that metadata is rendered into the wiki's citation system

The key product implication: the UI is only the front door. The experience is only as good as the metadata extraction and template-mapping system behind it.

## How Citoid Appears In The UI

When both VisualEditor's citation tool and Citoid are configured, the editor
shows a `Cite` button rather than a simple cite dropdown. Clicking that button
opens a dialog with three distinct tabs:

- `Automatic`
- `Manual`
- `Re-use`

That division matters. Wikimedia did not collapse all citation behavior into one
search field with one result list. It exposes three separate user intents:

- "find or generate a citation from an external source-like input"
- "build or edit a citation manually"
- "re-use a citation that already exists in the current page"

### Automatic

The `Automatic` tab is the most Citoid-specific part of the experience.

The docs say users can enter:

- a URL
- an ISBN
- a DOI
- a PMID
- a PMCID, including the `PMC` prefix
- a Wikidata QID
- a title
- a citation string

The behavior is intentionally broad: the user does not have to tell the system
what kind of thing they are entering. The system attempts to identify it and
generate an appropriate citation template.

The strongest examples are identifier-driven:

- paste a website address
- paste a book ISBN
- paste a paper DOI
- paste a PubMed identifier

These inputs are concrete and high-signal. They carry strong lookup value and
let the system do most of the work.

### Manual

The `Manual` tab is the escape hatch and power-user path.

The docs describe two manual flows:

- choose a standard citation template such as book, web, or journal
- use a simpler `Basic` reference form

The template flow is still form-driven. The editor opens the template editor,
marks required fields, lets the user hide optional fields, and supports adding
undocumented parameters.

The `Basic` path is looser. It allows the user to type a citation by hand,
including formatting, and optionally insert templates from inside that dialog.

This is important as a design pattern: automatic generation is not treated as a
complete replacement for manual editing. The official UX assumes that users need
a reliable fallback when generated metadata is incomplete, unsupported, or not
trusted.

### Re-use

The `Re-use` tab is easy to underestimate, but it is one of the strongest parts
of the overall workflow.

If the page already contains a citation relevant to the text being edited, the
user can:

- open `Cite`
- choose `Re-use`
- search within the page's existing citations
- insert the already-existing reference again

The docs explicitly mention a search field labeled `Search within current
citations` to filter long lists.

This is not just a convenience feature. It acknowledges a real authoring
pattern: citation work is often repetitive within one page or one editing
session, and making users recreate the same reference over and over would be
wasteful.

## How Citoid Handles Editing And Conversion

The docs describe several nearby behaviors that matter for UX even though they
are not part of the initial autocomplete step.

### Editing an existing reference

When a user clicks an existing citation marker, the editor can reopen the
associated citation UI. If the citation was created with a template, the user is
taken back into the template editor. If it is a `Basic` reference, the editor
opens the more freeform reference dialog.

This means Citoid is not only an insertion tool. It participates in an edit
loop.

### Converting a bare link to a fuller citation

The docs also mention that when a `Basic` reference contains only a link, the
user may be offered a `Convert` option. That attempts to run the automatic
feature and replace the simple reference with a more fully formatted reference.

That is a useful pattern to note: the system can upgrade low-structure input
after the fact, not only at the initial point of insertion.

## Important Details From The Official Docs

The official documentation contains several constraints and warnings that are
easy to miss but very important for product research.

### Title search is weaker than identifier input

The docs explicitly warn that users should be as specific as possible when
typing a title or citation string, because the search feature returns only the
first result from WorldCat and Crossref, "in a random order."

That is a remarkably candid warning. It implies:

- free-text lookup is materially less trustworthy than URL / ISBN / DOI lookup
- the UI may appear precise even when the underlying match is not
- "automatic" does not mean "confident"

This is one of the clearest official statements about where the workflow is
strong and where it becomes fuzzy.

### Citoid depends on Zotero translator coverage

The docs explain that Citoid relies on Zotero translators for much of the
"magic." If a site lacks a good translator, Citoid may produce only basic
information.

That creates an important UX boundary:

- some source domains are richly supported
- others are only partially understood
- unsupported sites can still produce a degraded result instead of a perfect one

The product lesson is not merely technical. The user experience of an automatic
citation tool is inseparable from source coverage.

### "We couldn't make a citation for you" is a normal state

The docs devote troubleshooting space to the error case where the system cannot
generate a citation.

They distinguish between:

- configuration failures
- broken template maps
- cache issues
- URL-specific failures where the source itself just cannot be interpreted

This matters because it frames failure as an expected state to design for, not
an edge case to hand-wave away.

### Citoid is template-driven under the hood

The Citoid configuration docs explain that local wikis map native Citoid types
such as `book`, `website`, `journalArticle`, `tvBroadcast`, and many others to
local citation templates.

The docs mention 34 native Citoid types and say the local wiki should map every
one of them to some template, even if the match is imperfect.

That tells us the user-facing flow is generic, but the output system is highly
structured. The UI can stay simple because the template layer absorbs much of
the formatting complexity.

## Web2Cit As A Related Layer

[Web2Cit](https://meta.wikimedia.org/wiki/Web2Cit) is not the same product as
Citoid, but it is relevant background.

Its own Meta page describes it as collaborative automatic citations for web
sources, and it is explicitly framed as improving the automatic citation story
for Wikipedia. Conceptually, it sits alongside Citoid as an effort to improve
coverage and quality for web-source extraction.

This is useful context because it reinforces a larger point:

- a citation UI may appear to be "just a form"
- in practice, the quality ceiling is determined by how good the source
  extraction layer is
- ecosystems that care about citation UX eventually invest in source-knowledge
  infrastructure, not only frontend polish

## Worked Examples From The Docs

The official docs repeatedly use concrete examples that are worth preserving
because they show the shape of the intended interaction.

### Example: cite from a URL

The user opens `Cite`, stays on `Automatic`, pastes a website address, and the
system attempts to generate a full citation template.

This is the cleanest path because the user provides one high-signal input and
the system does the rest.

### Example: cite from a book ISBN

The user enters an ISBN in the automatic field. Citoid attempts to resolve the
book and generate a cite-book style template from the resulting metadata.

This is a very strong fit for the automatic flow because ISBN is specific and
structured.

### Example: reuse a previously inserted citation

If the page already contains the relevant source, the user goes to `Re-use`,
searches within current citations, and inserts that existing footnote again
without recreating it.

This reduces repeated work and helps preserve consistency.

### Example: convert a simple link into a richer reference

If a basic reference contains only a URL, the editor may offer `Convert`, which
attempts to run the automatic citation path and upgrade the citation to a fuller
form.

This shows that the system supports progressive enrichment rather than requiring
perfect structured input on the first try.

## Lessons

The lessons below are intentionally generic. They are not yet product decisions.

### 1. Separate user intents explicitly

Citoid does not force `automatic`, `manual`, and `reuse` into one undifferentiated
result list. It gives each a distinct mode.

The lesson is that citation authoring usually contains multiple different
intentions:

- find an existing thing
- generate from an external identifier
- enter something manually
- re-use something already present

Treating those as separate modes reduces ambiguity.

### 2. Start from the cheapest high-confidence input

The automatic flow is strongest when the user can provide a URL, ISBN, DOI, or
other concrete identifier. That minimizes required typing while maximizing
lookup confidence.

The lesson is that a good citation UX should begin with the smallest useful
input that has strong disambiguation power.

### 3. Free-text search and identifier lookup are not the same interaction

The docs' warning about title search returning only a first result from
providers in effectively arbitrary order is important. It shows that free-text
lookup feels similar to identifier lookup in the UI but has much weaker
guarantees.

The lesson is that systems should not treat "paste a DOI" and "type a rough
title" as equally trustworthy inputs just because both happen in the same field.

### 4. Reuse is a first-class citation workflow

The existence of a dedicated `Re-use` tab shows that repeated citation work is
common enough to deserve its own path.

The lesson is that citation UX is not only about search and creation. It is
also about avoiding duplicate effort during an editing session or within one
document.

### 5. Automatic systems still need a credible manual fallback

Citoid keeps `Manual` close at hand rather than pretending automation will
always succeed. The docs repeatedly acknowledge partial metadata, unsupported
sites, and conversion limits.

The lesson is that users trust automatic tools more when there is a visible,
reliable way to correct or complete the result.

### 6. Failure states deserve intentional UX

The official docs treat "we couldn't make a citation for you" as a normal
design state with specific causes.

The lesson is that citation tools need good degraded behavior:

- clear empty states
- clear unsupported-source states
- a path forward when auto-generation fails

### 7. The metadata pipeline is part of the UX

Because Citoid depends on Zotero translators and template maps, the visible UI
quality depends heavily on invisible extraction infrastructure.

The lesson is that citation UX cannot be evaluated only at the component level.
If metadata extraction is weak, the user experiences the product as weak no
matter how polished the dropdown looks.

### 8. Structured output can sit behind a simple entry flow

Citoid's entry flow is simple, but its output is heavily structured through
template mapping and document-type handling.

The lesson is that a system can keep authoring lightweight while still
maintaining rich structured citation data and formatting rules underneath.
