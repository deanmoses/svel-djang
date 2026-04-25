import { describe, it, expect } from 'vitest';
import { CATALOG_META, type CatalogEntityKey } from './catalog-meta';

// Maps SvelteKit route directory → CATALOG_META key. Every entity route
// directory (whose dynamic segment is either `[slug]/` or `[...path]/`,
// optionally with a param matcher like `[...path=singleSegment]/`) that
// corresponds to a registry entity must be listed here.
const ROUTE_DIR_TO_KEY: Record<string, CatalogEntityKey> = {
  titles: 'title',
  models: 'model',
  manufacturers: 'manufacturer',
  franchises: 'franchise',
  series: 'series',
  people: 'person',
  cabinets: 'cabinet',
  'display-types': 'display-type',
  'display-subtypes': 'display-subtype',
  'game-formats': 'game-format',
  'reward-types': 'reward-type',
  tags: 'tag',
  'technology-generations': 'technology-generation',
  'technology-subgenerations': 'technology-subgeneration',
  'corporate-entities': 'corporate-entity',
  'gameplay-features': 'gameplay-feature',
  systems: 'system',
  themes: 'theme',
  'credit-roles': 'credit-role',
};

// Route directories that intentionally do NOT map to a CATALOG_META entry.
// Add to this list when introducing a route that should not be registry-managed.
const UNMAPPED_ROUTE_DIRS = new Set([
  'locations', // multi-segment [...path] catch-all, not yet in CATALOG_META
]);

// Match either `[slug]` or `[...whatever]` (with or without a param matcher).
const ENTITY_ROUTE_RE = /\/src\/routes\/([^/]+)\/(?:\[slug\]|\[\.\.\.[^\]]+\])/;

// Broad glob over every route file; filtering to entity-shaped paths happens
// in JS via ENTITY_ROUTE_RE so we don't have to enumerate matcher suffixes
// (e.g. `[...path=singleSegment]`) in the glob pattern itself.
const ALL_ROUTE_FILES = import.meta.glob('/src/routes/**/+*', { eager: false });

describe('catalog-meta vs route tree', () => {
  it('every entity route directory is either mapped or explicitly unmapped', async () => {
    const routeDirs = new Set(
      Object.keys(ALL_ROUTE_FILES)
        .map((p) => p.match(ENTITY_ROUTE_RE)?.[1])
        .filter((d): d is string => typeof d === 'string'),
    );

    for (const dir of routeDirs) {
      const mapped = dir in ROUTE_DIR_TO_KEY;
      const unmapped = UNMAPPED_ROUTE_DIRS.has(dir);
      expect(
        mapped || unmapped,
        `Route directory "${dir}" has a [slug]/ route but is not in ROUTE_DIR_TO_KEY or UNMAPPED_ROUTE_DIRS. ` +
          `Either add it to CATALOG_META + ROUTE_DIR_TO_KEY or mark it explicitly unmapped.`,
      ).toBe(true);

      if (mapped) {
        const key = ROUTE_DIR_TO_KEY[dir];
        expect(CATALOG_META).toHaveProperty(key);
      }
    }
  });

  it('every entity_type_plural matches the expected route directory', () => {
    for (const [dir, key] of Object.entries(ROUTE_DIR_TO_KEY)) {
      if (key in CATALOG_META) {
        expect(CATALOG_META[key].entity_type_plural).toBe(dir);
      }
    }
  });

  it('every CATALOG_META key maps to a known route directory', () => {
    // Guards against the generator emitting a key that has no corresponding
    // frontend route — without this, CatalogEntityKey widens silently and
    // helpers produce URLs that route to nothing.
    const knownKeys = new Set(Object.values(ROUTE_DIR_TO_KEY));
    for (const key of Object.keys(CATALOG_META) as CatalogEntityKey[]) {
      expect(
        knownKeys,
        `CATALOG_META contains "${key}" but no route directory maps to it. ` +
          `Add the mapping to ROUTE_DIR_TO_KEY and create the corresponding route.`,
      ).toContain(key);
    }
  });

  // Every linkable entity must have edit-history/ and sources/ subroutes.
  // These are thin wrappers over $lib/provenance-loaders and $lib/components,
  // but each entity still needs its own +page.server.ts + +page.svelte so the
  // files live under the entity's shared +layout.server.ts — otherwise
  // navigating to edit-history re-runs the entity load. The cost of this
  // requirement is ~10 lines of boilerplate per entity; the cost of forgetting
  // is an invisible UX gap (see credit-role, missing for an unknown period).
  describe.each(['edit-history', 'sources'])('%s subroute', (subroute) => {
    // Resolve each entity's dynamic segment (`[slug]` vs `[...<param>]`) by
    // peeking at any route file under its plural.
    const dynSeg = (plural: string): string => {
      const re = new RegExp(`^/src/routes/${plural}/(\\[[^\\]]+\\])/`);
      for (const p of Object.keys(ALL_ROUTE_FILES)) {
        const m = p.match(re);
        if (m) return m[1];
      }
      return '[slug]'; // fall back; the assertions below will fail informatively
    };

    it.each(Object.keys(CATALOG_META) as CatalogEntityKey[])(
      '%s has +page.server.ts and +page.svelte',
      (key) => {
        const plural = CATALOG_META[key].entity_type_plural;
        const base = `/src/routes/${plural}/${dynSeg(plural)}/${subroute}`;
        expect(ALL_ROUTE_FILES).toHaveProperty(`${base}/+page.server.ts`);
        expect(ALL_ROUTE_FILES).toHaveProperty(`${base}/+page.svelte`);
      },
    );
  });
});
