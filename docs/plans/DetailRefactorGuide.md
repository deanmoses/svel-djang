# Detail Refactor Guide

This document only covers traps and rationale that reading the current code doesn't reveal.

## Reference Examples

- **One-off record type (unique shape):** [models/[slug]/](../../frontend/src/routes/models/%5Bslug%5D/) — full-featured, inline scaffolding in the layout.
- **Family of near-identical entities, simple (no sidebar):** [display-types/[slug]/](../../frontend/src/routes/display-types/%5Bslug%5D/) wrapping [SimpleTaxonomyDetailLayout.svelte](../../frontend/src/lib/components/SimpleTaxonomyDetailLayout.svelte).
- **Family of near-identical entities, hierarchical (sidebar + mobile meta bar + optional media):** [gameplay-features/[slug]/](../../frontend/src/routes/gameplay-features/%5Bslug%5D/) using [TaxonomyDetailBaseLayout.svelte](../../frontend/src/lib/components/TaxonomyDetailBaseLayout.svelte) directly.

## When to extract a shared base

- **One-off record type:** inline scaffolding in the entity's `+layout.svelte`. No base.
- **Family of 3+ near-identical entities:** parameterized base + thin per-entity wrappers (e.g. `TaxonomyDetailBaseLayout`). Family-level shared context is fine — one `*EditActionContext` typed on the shared key union, not one per entity.

## Rationale (the _why_ behind the seams)

- **Desktop modal editing + mobile section routes.** The contract: one open editor at a time (desktop modal enforces it trivially) **and** real back-button semantics on mobile (section routes give each editor a URL). Collapsing to one mode breaks one invariant.
- **Layout owns `editAction`, pages consume via context.** Pages never branch on `isMobile`. The layout already knows whether to open a modal or navigate; pushing that decision into pages clones it into every accordion `[edit]` link.
- **Per-entity editor-dispatch component (`*EditorSwitch.svelte`).** The `{#if sectionKey === 'x'}` cascade lives in exactly one place; the layout's `SectionEditorHost` and the mobile `[section]/+page.svelte` both render the switch.
- **Typed `initialData`.** Use `Pick<components['schemas']['…']>` for single-schema editors; use a structural superset when the view must satisfy multiple schemas (e.g. `SimpleTaxonomyEditView`, `HierarchicalTaxonomyEditView`).
- **Sidebar/accordion `[edit]` hooks only when the block maps 1:1 to a real section.** A link that opens the wrong editor teaches the UI to lie.

## Avoid

- **Reading local state inside the URL→state effect that writes it.** In the `?edit=<segment>` sync pattern, effect 1 (URL→state) must write `editing` unconditionally. An `if (editing !== nextEditing)` guard turns `editing` into a read-dep of effect 1, which re-runs on local writes and reverts the user's click in the same tick. Same-value `$state` writes are already no-ops; the guard is wrong, not an optimization.
- **Defensive rendering of fields an invariant says won't exist.** Enforce the invariant at write time **and** strip the field from the API schema — otherwise the read side grows permanent dead branches that drift from the rule.
- **Hand-rolled `isEdit` / `isMedia` / `isSources` per record.** Use `resolveDetailSubrouteMode()`.
- **Forgetting `sidebarDesktopOnly={isDetail}` when the main column duplicates the sidebar on mobile.** `RecordDetailShell` defaults `sidebarDesktopOnly={false}`, which stacks the sidebar _below_ main content on mobile. When the detail page also renders a mobile meta bar / children accordion / relationships accordion, the sidebar must be suppressed on mobile (`={isDetail}` keeps it visible on subroutes that don't duplicate).
- **Generic "detail page framework" for one-off entities.** Three isomorphic layouts that share named helpers beats one configurable layout that tries to cover every case. Family bases are a different category — they're for 3+ near-identical entities, not for one-offs.
- **Bundling References with Overview.** Use `createRichTextAccordionState()` + split components (`RichTextOverviewAccordion` + `RichTextReferencesAccordion`) so each page places the two accordions independently. Otherwise References silently rides up past intermediate sections.
- **Accordion empty states.** When a block has no content, hide the accordion entirely — never render "No X yet" inside.
- **Multiple owners for URL sync or modal state.** One owner per concern.
- **`:global` in Svelte component styles.** Rearchitect; don't escape the scope.
- **Stringly-keyed contexts.** Use Symbol-keyed `createEditActionContext`.

## Lessons from Prior Refactors

Bugs whose fixes aren't visible in the current code.

- **Reactivity if-guard in URL sync.** Shipped into manufacturer, propagated to model and title; reverted every menu click on desktop. Fix: drop the guard. See `Avoid`.
- **References adjacent to Overview.** `RichTextAccordionSections` bundled both accordions. Worked on manufacturer's short page; broke title/model where seven sections separate them. Fix: split into two components with a shared state factory.
- **`title_description` dead field.** Backend serialized `title_description` on single-model titles even though the invariant said only the model owns description. Model detail grew a defensive dual-render branch. Fix: drop from the API schema **and** remove the defensive branch.
- **Mixed-edit citation warning miscategorization.** Manufacturer Name section (name + slug) was flagged `true`, then flipped to `false`. Rule of thumb: `true` when the section's fields genuinely come from multiple sources (Basics, External Data); `false` when they share a citation source in practice (Name, Description).
- **Flash of wrong UI on desktop deep-links.** Visiting `/x/slug/edit/name` on desktop briefly rendered the mobile edit shell before redirecting. Fix: gate the shell on `{#if isMobile === true}` and have `createIsMobileFlag` return the browser's synchronous `matchMedia` value on first paint.
- **Alias filter ported to the wrong entity.** Hierarchical-taxonomy refactor silently ported gameplay-features' `displayAliasesFor` (filters aliases whose normalized form equals the entity name) to themes, which historically never filtered. Themes aliases disappeared from the sidebar. Lesson: when extracting shared components from multiple entity layouts, verify each entity's pre-refactor behavior per-entity; don't assume the family is uniform.
- **Mobile sidebar double-rendering.** `TaxonomyDetailBaseLayout` passed `sidebar` through to `RecordDetailShell` without `sidebarDesktopOnly`. Result: on mobile, the sidebar stacked below the main column which was already rendering its content via mobile meta bar + children accordion. Fix: pass `sidebarDesktopOnly={isDetail}` — keeps the sidebar visible on subroutes (`/sources`, `/edit-history`) where the main column doesn't duplicate it.
- **Prettier collapsing template whitespace.** `{#if i > 0}, {/if}<a>` inside `{#each}` had prettier reformat the comma-space across lines, and Svelte's whitespace handling stripped it — `"Blackjack, Cards"` became `"Blackjack,Cards"`. Fix: wrap literal separators in a span (`<span class="sep">, </span>`) so the whitespace is element content, not inter-tag whitespace. Add a regression test that asserts `textContent` contains the expected separator.
- **`SearchableSelect` showing single-selected label in the input.** In multi mode with exactly one selection, the input value was populated with that item's label, reading like a pre-filled search query and duplicating the chip below. Fix: in multi mode, only populate the input for 2+ selections (show "N selected"); leave it empty for 0 or 1 and let the chips speak.
