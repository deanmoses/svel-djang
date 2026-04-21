# Detail Layout Patterns

Architectural guidance for building catalog-entity detail pages (the accordion reader + section-based edit). Read this before starting work on a new entity's detail layout or touching a shared one.

Site-specific traps live inline at their sites, not here. If you're about to edit a file and wonder _why_ a particular pattern is shaped the way it is, check the comment there first.

## Picking a scaffold

Three shapes. Pick one, copy the matching reference.

| Shape                                                  | Reference                                                                                                                                                                                 | Notes                                                                                                                                                 |
| ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **One-off** — unique shape (Model, Title, System, …)   | [models/[slug]/](../frontend/src/routes/models/%5Bslug%5D/)                                                                                                                               | Inline scaffolding in the entity's `+layout.svelte`. No base component.                                                                               |
| **Simple family** — near-identical, no sidebar         | [display-types/[slug]/](../frontend/src/routes/display-types/%5Bslug%5D/) wrapping [SimpleTaxonomyDetailLayout.svelte](../frontend/src/lib/components/SimpleTaxonomyDetailLayout.svelte)  | Thin per-entity wrapper around the shared layout.                                                                                                     |
| **Hierarchical family** — near-identical, with sidebar | [gameplay-features/[slug]/](../frontend/src/routes/gameplay-features/%5Bslug%5D/) using [TaxonomyDetailBaseLayout.svelte](../frontend/src/lib/components/TaxonomyDetailBaseLayout.svelte) | Sidebar + mobile meta bar + optional media. Family-level shared context (one `*EditActionContext` typed on the shared key union, not one per entity). |

**Threshold for extracting a shared base**: three near-identical entities. Below that, inline the scaffolding per entity. Three isomorphic layouts sharing named helpers beats one configurable layout that tries to cover every case.

## Load-bearing invariants

- **Desktop modal editing + mobile section routes.** One open editor at a time (desktop modal enforces it trivially) **and** real back-button semantics on mobile (section routes give each editor a URL). Collapsing to one mode breaks one invariant.
- **Layout owns `editAction`, pages consume via context.** Pages never branch on `isMobile`. The layout already knows whether to open a modal or navigate; pushing that decision into pages clones it into every accordion `[edit]` link.
- **One `*EditorSwitch.svelte` per entity.** The `{#if sectionKey === 'x'}` cascade lives in exactly one place; the layout's `SectionEditorHost` and the mobile `[section]/+page.svelte` both render it.
- **Typed `initialData`.** Use `Pick<components['schemas']['…']>` for single-schema editors; use a structural superset when the view must satisfy multiple schemas (e.g. `SimpleTaxonomyEditView`, `HierarchicalTaxonomyEditView`).
- **Sidebar/accordion `[edit]` hooks only when the block maps 1:1 to a real section.** A link that opens the wrong editor teaches the UI to lie.
- **One owner per concern.** URL sync and modal state each need a single source of truth.
- **No `:global` in Svelte component styles.** Rearchitect instead of escaping the scope.
- **Symbol-keyed contexts, not strings.** Use `createEditActionContext`.

## When extracting shared components

Verify each entity's pre-refactor behavior individually — don't assume the family is uniform. A shared-component extraction once silently ported gameplay-features' alias-filtering rule onto Themes, which had never filtered. Check entity-by-entity; tests per entity are cheap insurance.
