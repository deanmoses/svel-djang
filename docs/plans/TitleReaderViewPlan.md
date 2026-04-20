# Title Reader View — Implementation Plan

Sibling to [ModelAndTitleUX.md](ModelAndTitleUX.md), which captures the design decisions. This doc is the implementation-sequencing plan for the **reader view only**. Edit flows are a separate milestone.

## Scope

Implement the section-based reader for Title detail pages, both multi-model and single-model variants. Replaces the current tab-based layout. Out of scope for this milestone:

- Title edit sections (both variants)
- "Change Title" / structural move action
- `needs_review` surfacing

## Phase 1 — Backend aggregation

Goal: title-detail API returns data shaped for the section-based reader, with the aggregation rules from [ModelAndTitleUX.md](ModelAndTitleUX.md) applied.

1. Extend the response in `backend/apps/catalog/api/titles.py`:
   - Multi-model: return aggregated `technology`, `features` (intersection, including M2M themes / gameplay / reward_types / tags), `people` (intersection on `(person, role)`), `media` (union), `related_titles` (union of `converted_from` / `remake_of` across models, each labeled with its source model).
   - Single-model: continue returning `model_detail` as today.
   - Title-level fields (franchise, series, opdb_group_id, fandom_page_id, abbreviations) returned as-is.

2. **Check first:** sidebar aggregation logic likely already exists — reuse rather than re-implement. If it lives in a sidebar-specific place, lift it into a shared helper.

3. Tests — one per rule:
   - Scalar intersection: year agrees → show; disagrees → hide
   - M2M intersection: overlapping theme set across models
   - People intersection: credit matches on `(person, role)`
   - Media union: all images across all models
   - Related titles union: each cross-title link surfaces with its originating model label

## Phase 2 — Shared reader primitives

4. Audit what's reusable from the Model reader work (sections, `AccordionSection`, thumbnail card). Lift anything shared between Model and Title readers into `frontend/src/lib/components/readers/` (or similar).

5. `hideIfEmpty` helper / pattern — each section returns null when its data is empty, so accordion order collapses cleanly.

6. References extractor — Markdown-reference / footnote extractor pulled from whichever Description is visible. Shared utility; used by both Model and Title readers.

## Phase 3 — Multi-model title reader

7. Replace the tab-based UI in `frontend/src/routes/titles/[slug]/+layout.svelte` and `+page.svelte` for the multi-model path. Accordion sections, in order:
   - Overview (Title.Description)
   - Models (flat thumbnail grid — no hierarchy, variants appear at the same level as top-level models)
   - Technology
   - Features (with franchise or series included)
   - Related Titles
   - People
   - Media
   - External Links (OPDB group, Fandom)
   - References

8. Top-bar:
   - Edit menu → `/titles/[slug]/edit/[section]`
   - History
   - Tools → Sources

## Phase 4 — Single-model title reader

9. Replace the current `ModelDetailBody` render path for single-model titles. Compose Model reader sections + franchise/series inside Features + Related Titles + title-level External Links merged with model-level external IDs.

10. Action bar with **two labeled edit dropdowns** per the separate-edit decision:
    - "Edit Title" dropdown — title-tier sections (Basics, External Data). Each item navigates to `/titles/[slug]/edit/[section]`.
    - "Edit Model" dropdown — model-tier sections (Overview, Technology, Features, etc.). Each item navigates to `/models/[modelSlug]/edit/[section]`.

    History and Sources remain single title-tier links on the action bar (unchanged from today). Revisit per-tier split only if it feels missing in practice.

## Phase 5 — Tests, cleanup, responsive check

11. Component tests per section with representative aggregation fixtures.
12. Snapshot / integration tests: single-model and multi-model page flows.
13. Remove the old tab-based title layout code once migrated.
14. Mobile check — tabs were the original pain point; verify accordions feel right on narrow viewports.

## Dependencies & parallelism

- Phase 1 and Phase 2 are independent; can run in parallel (frontend against mocked API data).
- Phase 3 depends on Phases 1 + 2.
- Phase 4 depends on Phase 3 (shares section components) plus the Model reader work (already landed).
- References extraction (in Phase 2) is standalone and can land anytime.

## Open questions

- **History / Sources scope for single-model titles** — kept title-tier only for this tranche. Revisit per-tier split only if it feels missing in practice.
- **Aggregation helper location** — where does the existing sidebar logic live, and does it already expose what we need? Drives whether Phase 1 is "extend" or "extract + extend."
- **"Hide if none" on Models section** — won't fire in practice (multi-model = ≥2 models post-FK-NOT-NULL). Keep as defensive default or drop? Suggest keep; costs nothing.
- **Combined single-model edit menu** — this tranche ships two separate dropdowns. If a combined single-menu feels better after use, migrate to a tier-aware registry with dual-slug plumbing in a follow-up.
