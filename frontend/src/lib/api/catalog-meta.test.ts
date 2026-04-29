import { describe, it, expect } from 'vitest';
import { CATALOG_META, type CatalogEntityKey } from './catalog-meta';

// Maps SvelteKit route directory → CATALOG_META key + the dynamic-segment
// shape its detail routes use. Most entities use single-segment `[slug]`;
// Location uses `[...path]` because its public_id is a multi-segment
// `location_path` (e.g. `usa/il/chicago`). Every detail route that
// corresponds to a registry entity must be listed here.
type RouteSegment = '[slug]' | '[...path]';
const ROUTE_DIR_TO_KEY: Record<string, { key: CatalogEntityKey; segment: RouteSegment }> = {
  titles: { key: 'title', segment: '[slug]' },
  models: { key: 'model', segment: '[slug]' },
  manufacturers: { key: 'manufacturer', segment: '[slug]' },
  franchises: { key: 'franchise', segment: '[slug]' },
  series: { key: 'series', segment: '[slug]' },
  people: { key: 'person', segment: '[slug]' },
  cabinets: { key: 'cabinet', segment: '[slug]' },
  'display-types': { key: 'display-type', segment: '[slug]' },
  'display-subtypes': { key: 'display-subtype', segment: '[slug]' },
  'game-formats': { key: 'game-format', segment: '[slug]' },
  'reward-types': { key: 'reward-type', segment: '[slug]' },
  tags: { key: 'tag', segment: '[slug]' },
  'technology-generations': { key: 'technology-generation', segment: '[slug]' },
  'technology-subgenerations': { key: 'technology-subgeneration', segment: '[slug]' },
  'corporate-entities': { key: 'corporate-entity', segment: '[slug]' },
  'gameplay-features': { key: 'gameplay-feature', segment: '[slug]' },
  systems: { key: 'system', segment: '[slug]' },
  themes: { key: 'theme', segment: '[slug]' },
  'credit-roles': { key: 'credit-role', segment: '[slug]' },
  locations: { key: 'location', segment: '[...path]' },
};

// Route directories that intentionally do NOT map to a CATALOG_META entry.
// Add to this list when introducing a route that should not be registry-managed.
const UNMAPPED_ROUTE_DIRS = new Set<string>([]);

// CATALOG_META keys whose frontend routes are deferred. The backend registers
// these (via LinkableModel) but the SvelteKit routes don't exist yet.
// See docs/plans/model_driven_metadata/LocationCrud.md for the location plan.
const DEFERRED_KEYS = new Set<CatalogEntityKey>(['location']);

describe('catalog-meta vs route tree', () => {
  it('every detail route directory is either mapped or explicitly unmapped', async () => {
    const slugRoutes = import.meta.glob('/src/routes/*/[slug]/+*', { eager: false });
    const pathRoutes = import.meta.glob('/src/routes/*/[...path]/+*', { eager: false });
    const detailRouteRe = /\/src\/routes\/([^/]+)\/\[(?:slug|\.\.\.path)\]/;
    const routeDirs = new Set(
      [...Object.keys(slugRoutes), ...Object.keys(pathRoutes)]
        .map((p) => p.match(detailRouteRe)?.[1])
        .filter((d): d is string => typeof d === 'string'),
    );

    for (const dir of routeDirs) {
      const mapped = dir in ROUTE_DIR_TO_KEY;
      const unmapped = UNMAPPED_ROUTE_DIRS.has(dir);
      expect(
        mapped || unmapped,
        `Route directory "${dir}" has a detail route but is not in ROUTE_DIR_TO_KEY or UNMAPPED_ROUTE_DIRS. ` +
          `Either add it to CATALOG_META + ROUTE_DIR_TO_KEY or mark it explicitly unmapped.`,
      ).toBe(true);

      if (mapped) {
        const { key } = ROUTE_DIR_TO_KEY[dir];
        expect(CATALOG_META).toHaveProperty(key);
      }
    }
  });

  it('every entity_type_plural matches the expected route directory', () => {
    for (const [dir, { key }] of Object.entries(ROUTE_DIR_TO_KEY)) {
      if (key in CATALOG_META) {
        expect(CATALOG_META[key].entity_type_plural).toBe(dir);
      }
    }
  });

  it('every CATALOG_META key maps to a known route directory', () => {
    // Guards against the generator emitting a key that has no corresponding
    // frontend route — without this, CatalogEntityKey widens silently and
    // helpers produce URLs that route to nothing.
    const knownKeys = new Set(Object.values(ROUTE_DIR_TO_KEY).map((entry) => entry.key));
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
    const slugFiles = import.meta.glob('/src/routes/*/[slug]/*/+page.*', { eager: false });
    const pathFiles = import.meta.glob('/src/routes/*/[...path]/*/+page.*', { eager: false });
    const files = { ...slugFiles, ...pathFiles };

    const segmentByKey = new Map<CatalogEntityKey, RouteSegment>(
      Object.values(ROUTE_DIR_TO_KEY).map((entry) => [entry.key, entry.segment]),
    );

    it.each((Object.keys(CATALOG_META) as CatalogEntityKey[]).filter((k) => !DEFERRED_KEYS.has(k)))(
      '%s has +page.server.ts and +page.svelte',
      (key) => {
        const plural = CATALOG_META[key].entity_type_plural;
        const segment = segmentByKey.get(key) ?? '[slug]';
        const base = `/src/routes/${plural}/${segment}/${subroute}`;
        expect(files).toHaveProperty(`${base}/+page.server.ts`);
        expect(files).toHaveProperty(`${base}/+page.svelte`);
      },
    );
  });
});
