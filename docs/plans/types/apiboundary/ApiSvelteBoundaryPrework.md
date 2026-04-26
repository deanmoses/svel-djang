# API Boundary Prework

## Context

Items carried over from the merged schema rationalization plan
(`refactor/api-schema-rationalization`) that should land before the
API boundary work in [ApiSvelteBoundary.md](ApiSvelteBoundary.md).

Two of these are deletion-heavy refactors: the rename sweep would
otherwise touch 13+ wrapper files and two duplicate 148-line layout
files that this prework removes. Doing them first turns those files
from "rename surface" into "files that don't exist anymore."

## Replace `saveClaims` callback prop with `claimsPath` prop

Both [HierarchicalTaxonomyEditorSwitch.svelte](../../../../frontend/src/lib/components/editors/HierarchicalTaxonomyEditorSwitch.svelte)
and [SimpleTaxonomyEditorSwitch.svelte](../../../../frontend/src/lib/components/editors/SimpleTaxonomyEditorSwitch.svelte)
take a `saveClaims` callback prop. Across all 13 routes that use
them, every wrapper is a trivial pass-through that exists only to
bind a path string — none add custom save behavior. The callback
contract is paying flexibility tax that zero callers are using.

Refactor: switches accept a `claimsPath` prop typed as
`SimpleTaxonomyClaimsPath` or `HierarchicalTaxonomyClaimsPath` (the
structurally-derived path constraints from
[save-claims-shared.ts](../../../../frontend/src/lib/components/editors/save-claims-shared.ts))
and call the appropriate shared save helper internally.

Eliminates:

- All 11 simple-taxonomy `save-*-claims.ts` wrappers (cabinets,
  credit-roles, display-subtypes, display-types, franchises,
  game-formats, reward-types, series, tags, technology-generations,
  technology-subgenerations).
- Both hierarchical `save-*-claims.ts` wrappers (themes,
  gameplay-features).
- The `SaveSimpleTaxonomyClaims` and `SaveHierarchicalTaxonomyClaims`
  callback type aliases.
- The franchises/series wrapper-location asymmetry — those wrappers
  sit at `[slug]/edit/save-X-claims.ts` while the other 9 sit at
  `[slug]/save-X-claims.ts`.

Routes shrink to e.g.
`<HierarchicalTaxonomyEditorSwitch claimsPath="/api/themes/{slug}/claims/" … />`.
If a route ever needs custom save behavior, reintroduce a callback
prop for that route — don't pre-pay across 13 callers.

Counter-consideration: the switch component takes on knowledge of API
endpoints. It's already coupled to domain (knows which sections map
to which sub-editors), so this is the same tier of coupling, not a
new layer violation.

## Series/Franchise full layout fold-in

The 11 simple taxonomies have 17-line `+layout.svelte` files that
delegate to [SimpleTaxonomyDetailLayout.svelte](../../../../frontend/src/lib/components/SimpleTaxonomyDetailLayout.svelte).
Series and franchises have 148-line `+layout.svelte` files
([series](../../../../frontend/src/routes/series/[slug]/+layout.svelte),
[franchises](../../../../frontend/src/routes/franchises/[slug]/+layout.svelte))
that diff only in `Series` ↔ `Franchise` substitution and import
paths. Same story for `edit/[section]/+page.svelte`.

**Why they opted out.** `SimpleTaxonomyDetailLayout` is hard-coded to
`SIMPLE_TAXONOMY_EDIT_SECTIONS` (the 3-section list with
`display-order`). Series/franchise legitimately need 2 sections —
their models genuinely have no `display_order`
([series.py:27-79](../../../../backend/apps/catalog/models/series.py#L27-L79):
both order by `name`, docstrings call out "manually-curated" and
"sparse"). Rather than teach the layout to accept a custom section
list, someone copy-pasted the entire layout machinery.

**`usesSectionEditorForm` background.** The flag is real and
load-bearing — read at
[TaxonomyEditSectionPageBase.svelte:98](../../../../frontend/src/lib/components/TaxonomyEditSectionPageBase.svelte#L98)
and
[SectionEditorHost.svelte:91-93](../../../../frontend/src/lib/components/SectionEditorHost.svelte#L91-L93)
to gate form-host vs. immediate-active editor flow. Several real
sections set it `false`. `SIMPLE_TAXONOMY_EDIT_SECTIONS` omits it
because `SimpleTaxonomyDetailLayout` and
`SimpleTaxonomyEditSectionPage` inject `usesSectionEditorForm: true`
inline at consumption — simple-taxonomy sections always use the form
host. Series/franchise carry the flag on the section def because they
bypass that injection. Folding them back into the simple-taxonomy
layout means the flag stops appearing in their section defs.

**Refactor.** Add an optional `sections` (or
`excludeSections={['display-order']}`) prop to
`SimpleTaxonomyDetailLayout` and `SimpleTaxonomyEditSectionPage`.
Series and franchise routes then become 17-line layouts like the
other 11.

Combined with the `claimsPath`-prop refactor above, eliminates:

- 2× 148-line `+layout.svelte` files → 17-line wrappers.
- 2× bloated `edit/[section]/+page.svelte` files → simple delegations.
- 2× `*EditorSwitch.svelte` files (subsumed by the generic switch via
  `claimsPath`).
- 2× `*-edit-sections.ts` files (the 2-section list passes inline).
- 2× `*-edit-types.ts` files (subsumed by `SimpleTaxonomyEditView`).
- 2× `save-*-claims.ts` files (subsumed by `claimsPath`).
- The wrapper-file location asymmetry resolves naturally (no
  wrappers).
