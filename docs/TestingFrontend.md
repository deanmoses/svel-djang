# Frontend Testing

Frontend tests use `vitest`.

## What to Test

- TypeScript module logic
- component behavior where UI wiring matters
- data-shape expectations against the API contract where appropriate

Prefer testing logic in small TypeScript units where possible rather than over-relying on broad UI tests.

## Test Tiers

The frontend has two vitest **projects** (configured in `vitest.config.ts`) that run in different environments:

| Project | Environment | File pattern    | What to test                                                |
| ------- | ----------- | --------------- | ----------------------------------------------------------- |
| `unit`  | Node        | `*.test.ts`     | Pure functions, SSR renders (`svelte/server`), data helpers |
| `dom`   | jsdom       | `*.dom.test.ts` | Component interactions, event handling, DOM behavior        |

Both run together via `pnpm test`. For focused iteration:

```bash
pnpm test:unit        # unit tests only
pnpm test:dom         # DOM tests only
pnpm test:dom:watch   # DOM tests in watch mode
```

## Creating a DOM Test

Name the file `*.dom.test.ts` next to the component. The `.dom.` suffix routes it to the jsdom project automatically. Use `@testing-library/svelte` for rendering and queries, `userEvent` for interactions. See `wikilink-autocomplete.dom.test.ts` for the canonical example.

**Gotcha:** when calling exported component methods directly (e.g. `handleExternalKeydown`), wrap in `flushSync` from `svelte` — DOM updates from direct method calls are not automatically flushed.

### jsdom Polyfills

The DOM project loads `src/tests/setup-dom.ts` which provides:

- `@testing-library/jest-dom/vitest` — DOM matchers (`toBeInTheDocument()`, `toHaveTextContent()`, etc.)
- `Element.prototype.scrollIntoView` — no-op (jsdom doesn't implement it)
- `document.execCommand` — returns `false` (triggers manual text insertion fallbacks)

## DOM Test Patterns

These patterns are established in the wikilink autocomplete tests. Follow them when adding new DOM tests.

### Shared mock data

When multiple test files mock the same API module, extract the data to a shared fixtures file rather than duplicating it. Vitest's `vi.mock` factories are hoisted above imports, so they can't reference regular imports. Use an async factory with dynamic import:

```typescript
import { SEARCH_RESULTS } from "./link-types-fixtures";

vi.mock("$lib/api/link-types", async () => {
  const f = await import("./link-types-fixtures");
  return {
    fetchLinkTypes: vi.fn().mockResolvedValue(f.LINK_TYPES),
    searchLinkTargets: vi.fn().mockResolvedValue({ results: f.SEARCH_RESULTS }),
  };
});
```

Import the data directly (non-hoisted) for use in test assertions.

### Mock reset between tests

Use `mockReset().mockResolvedValue(...)` in `afterEach`, not `mockClear()`. `mockClear` only clears call history — `mockResolvedValueOnce` overrides persist across tests unless the implementation is explicitly reset.

### Layered flow helpers

Extract multi-step setup into composable helpers that build on each other: `waitForTypes()` → `openSearch()` → select result. Individual tests stay short and focused on one assertion.

### Synchronous vs. async assertions

Only wait when the production code actually defers work. If the code path under test is synchronous (e.g. `handleInput` → `detectTrigger` for a single `[`), assert immediately — don't add `waitFor`, fake timers, or sleeps. Unnecessary waits teach the wrong pattern and hide whether the code is actually async.

### Test at the right layer

Timing mechanics (exact debounce delay, coalescing behavior, generation counters) belong in unit tests for the helper module. DOM tests should verify UI-visible outcomes: "typing updates results" and "stale response doesn't win." Over-coupling DOM tests to helper internals makes them fragile and duplicates coverage.

### Querying elements

Use accessible roles and names (`getByRole('combobox', { name: /search title/i })`) rather than CSS classes or test IDs. Tests survive refactors that change DOM structure as long as semantics are preserved.

### userEvent `[` workaround

`userEvent` treats `[` as a key-descriptor opener (`[[` = escape for a single literal `[`). For typing `[[` into a textarea, set the value directly and fire `fireEvent.input()` rather than fighting the parser. Document the workaround with a comment explaining why.
