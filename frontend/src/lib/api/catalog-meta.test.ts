import { describe, it, expect } from 'vitest';
import { CATALOG_META, type CatalogEntityKey } from './catalog-meta';

// Maps SvelteKit route directory → CATALOG_META key. Every [slug]/ route
// that corresponds to a registry entity must be listed here.
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
const UNMAPPED_ROUTE_DIRS = new Set<string>([]);

// CATALOG_META keys whose frontend routes are deferred. The backend registers
// these (via LinkableModel) but the SvelteKit routes don't exist yet.
// See docs/plans/model_driven_metadata/LocationCrud.md for the location plan.
const DEFERRED_KEYS = new Set<CatalogEntityKey>(['location']);

describe('catalog-meta vs route tree', () => {
  it('every [slug]/ route directory is either mapped or explicitly unmapped', async () => {
    const routes = import.meta.glob('/src/routes/*/[slug]/+*', { eager: false });
    const routeDirs = new Set(
      Object.keys(routes)
        .map((p) => p.match(/\/src\/routes\/([^/]+)\/\[slug\]/)?.[1])
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
      if (DEFERRED_KEYS.has(key)) continue;
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
    const files = import.meta.glob('/src/routes/*/[slug]/*/+page.*', { eager: false });

    it.each((Object.keys(CATALOG_META) as CatalogEntityKey[]).filter((k) => !DEFERRED_KEYS.has(k)))(
      '%s has +page.server.ts and +page.svelte',
      (key) => {
        const plural = CATALOG_META[key].entity_type_plural;
        const base = `/src/routes/${plural}/[slug]/${subroute}`;
        expect(files).toHaveProperty(`${base}/+page.server.ts`);
        expect(files).toHaveProperty(`${base}/+page.svelte`);
      },
    );
  });
});
