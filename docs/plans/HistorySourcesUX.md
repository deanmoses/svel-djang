# History / Sources UX

## Finding

`Edit History` and `Sources` are not part of the primary record-reading flow. They are secondary, investigative views: users go there to inspect provenance, compare claims, and review past edits. Because of that, embedding them inside the normal detail-page shell makes them compete with context that is less important than the audit content itself.

## Recommendation

Present `Edit History` and `Sources` as standalone focus views rather than as content inside the regular detail page layout.

- Remove the normal detail sidebar and reader-style header chrome.
- Keep only lightweight record context, such as the entity name and a back link.
- Use dedicated routes on mobile.
- Treat any desktop modal or sheet as an optional quick-look affordance, not the primary presentation.

## Rationale

These views are long, reference-heavy, and task-focused. They benefit more from space, scanability, and clear navigation than from persistent detail-page framing. A standalone page is also a better canonical target for deep-linking and browser navigation than a modal.
