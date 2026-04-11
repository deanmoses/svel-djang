# Markdown Toolbar

Add a compact toolbar to `MarkdownTextArea` for the existing markdown authoring flow.

## Scope

- Add buttons for bold, italic, link, bulleted list, numbered list, and citation.
- Keep the textarea as the source of truth.
- Reuse the current markdown shortcut and wikilink/citation insertion logic.

## Visual

- Render a compact horizontal toolbar directly above the textarea.
- Use the existing `FaIcon` component and the installed `@fortawesome/free-solid-svg-icons` package.
- Button order: bold, italic, link, bulleted list, numbered list, citation.
- Icons: `faBold`, `faItalic`, `faLink`, `faListUl`, `faListOl`, `faBookOpen`.
- Each button needs a visible tooltip or accessible name matching the action label.

## Components

- Add a presentational `MarkdownToolbar.svelte` component for the toolbar UI only.
- `MarkdownToolbar.svelte` renders the buttons and emits callbacks for each action.
- `MarkdownTextArea.svelte` remains the owner of textarea state, selection handling, edit helpers, dropdown state, and link/citation insertion behavior.
- Place `MarkdownToolbar.svelte` next to `MarkdownTextArea.svelte` in `frontend/src/lib/components/form/`.

## Behavior

- Toolbar actions must apply at the current selection and preserve undo behavior.
- Bold, italic, and link call the existing edit helpers in `markdown-shortcuts.ts` via `applyAndSync()` — same code path as the keyboard shortcuts.
- List buttons toggle a bullet (`-`) or number (`1.`) prefix on selected lines (new helper in `markdown-shortcuts.ts`; the existing `listEnter` only handles continuation, not insertion).
- Citation button opens directly into the citation flow — no `[[` is inserted into the text and no type-picker step. `spliceLink()` handles a zero-width range (triggerStart === cursorPos) as a plain insertion, so the rest of the flow is unchanged.
- Internal links continue to use the existing `[[...]]` autocomplete flow.

## Implementation

- Extend `MarkdownTextArea.svelte` with a toolbar above the textarea.
- Toolbar clicks for bold, italic, and link call the existing helpers — no extraction needed.
- Add a `toggleList` helper to `markdown-shortcuts.ts` that prefixes/unprefixes selected lines with a bullet or number prefix.
- Add an `openLinkPicker(mode)` helper in `MarkdownTextArea.svelte` that sets `triggerStart` to the current cursor position and calls `openDropdown()` (preserving blur-timeout clearing and dropdown positioning). The citation button calls `openLinkPicker('cite')`, a future generic link button could call `openLinkPicker()` for the normal type picker.
- Add an `initialType` prop to `WikilinkAutocomplete.svelte` so it can start directly in the citation stage instead of the type picker. The stage logic already exists — this just lets it be entered from outside.

## Acceptance

- Editors can insert a citation without typing raw `[[`.
- Toolbar and keyboard shortcuts produce identical markdown output.
- Existing markdown textarea and citation tests are expanded to cover toolbar actions.

## Follow-up

- Consider reorganizing markdown editor components under `frontend/src/lib/components/form/markdown/` in a separate commit, if the directory feels crowded after the toolbar lands.
