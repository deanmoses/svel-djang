import { describe, expect, it } from 'vitest';
import {
  buildSchemaOrgNode,
  buildEntityJsonLd,
  buildListingJsonLd,
  listingMeta,
  type EntityBaseFacts,
} from './schema-org';
import type { EntityInfo, SchemaOrgInfo } from './types';
import {
  corporateEntity,
  creditRole,
  franchise,
  location,
  manufacturer,
  model,
  person,
  series,
  system,
  theme,
  title,
} from './index';
import type { LocationDetailSchema } from '$lib/api/schema';

const ORIGIN = 'https://flipcommons.org';
const PAGE = new URL(`${ORIGIN}/themes/fantasy`);

function entity(over: Partial<EntityBaseFacts> = {}): EntityBaseFacts {
  return {
    name: 'Fantasy',
    public_id: 'fantasy',
    last_modified: '2026-05-29T16:12:08.340Z',
    description: { text: '', html: '', plain: 'Dragons and wizards.', citations: [] },
    ...over,
  };
}

function info(
  schemaOrg: EntityInfo<EntityBaseFacts>['schemaOrg'],
  entityType: EntityInfo<EntityBaseFacts>['entityType'] = 'theme',
): EntityInfo<EntityBaseFacts> {
  return { entityType, schemaOrg };
}

/**
 * Build a node from a loosely-typed entity + schemaOrg, so tests can exercise
 * `fieldMap`/`relationshipMap` keys (e.g. `logo_url`, `manufacturer`) that
 * aren't on `EntityBaseFacts`. The casts are localized to this harness.
 */
function buildNode(
  ent: Record<string, unknown>,
  schemaOrg: SchemaOrgInfo<Record<string, unknown>>,
  entityType: EntityInfo<EntityBaseFacts>['entityType'] = 'theme',
  page: URL = PAGE,
) {
  return buildSchemaOrgNode(
    ent as unknown as EntityBaseFacts,
    { entityType, schemaOrg } as unknown as EntityInfo<EntityBaseFacts>,
    page,
  );
}

describe('buildSchemaOrgNode', () => {
  it('single type emits @type as a string', () => {
    const node = buildSchemaOrgNode(entity(), info({ types: ['DefinedTerm'] }), PAGE);
    expect(node['@type']).toBe('DefinedTerm');
    expect(node.name).toBe('Fantasy');
    expect(node.description).toBe('Dragons and wizards.');
  });

  it('emits dateModified from last_modified (ISO string, as-is)', () => {
    const node = buildSchemaOrgNode(
      entity({ last_modified: '2026-05-29T16:12:08.340Z' }),
      info({ types: ['DefinedTerm'] }),
      PAGE,
    );
    expect(node.dateModified).toBe('2026-05-29T16:12:08.340Z');
  });

  it('omits dateModified when last_modified is empty', () => {
    const node = buildSchemaOrgNode(
      entity({ last_modified: '' }),
      info({ types: ['DefinedTerm'] }),
      PAGE,
    );
    expect(node.dateModified).toBeUndefined();
  });

  it('multiple types emit @type as an array', () => {
    const node = buildSchemaOrgNode(entity(), info({ types: ['Game', 'ProductModel'] }), PAGE);
    expect(node['@type']).toEqual(['Game', 'ProductModel']);
  });

  it('function-form types are evaluated against the entity', () => {
    const node = buildSchemaOrgNode(
      entity({ public_id: 'sci-fi' }),
      info({ types: (e) => (e.public_id === 'sci-fi' ? ['DefinedTerm'] : ['Thing']) }),
      PAGE,
    );
    expect(node['@type']).toBe('DefinedTerm');
  });

  it('@id is the canonical /{plural}/{public_id} URL, independent of the page path', () => {
    const node = buildSchemaOrgNode(
      entity(),
      info({ types: ['DefinedTerm'] }),
      new URL(`${ORIGIN}/themes/fantasy/sources`),
    );
    expect(node['@id']).toBe(`${ORIGIN}/themes/fantasy`);
  });

  it('@id uses the entity_type_plural of the declared entityType', () => {
    const node = buildSchemaOrgNode(
      entity({ public_id: 'design' }),
      info({ types: ['Occupation'] }, 'credit-role'),
      PAGE,
    );
    expect(node['@id']).toBe(`${ORIGIN}/credit-roles/design`);
  });

  it('@id uses the full public_id path (Location), not a collapsed last segment', () => {
    const node = buildSchemaOrgNode(
      entity({ public_id: 'usa/il/chicago', name: 'Chicago' }),
      info({ types: ['City'] }, 'location'),
      new URL(`${ORIGIN}/locations/usa/il/chicago`),
    );
    expect(node['@id']).toBe(`${ORIGIN}/locations/usa/il/chicago`);
  });

  it('description is omitted when .plain is empty', () => {
    const node = buildSchemaOrgNode(
      entity({ description: { text: '', html: '', plain: '', citations: [] } }),
      info({ types: ['DefinedTerm'] }),
      PAGE,
    );
    expect(node).not.toHaveProperty('description');
  });

  it('description is omitted when .plain is only whitespace', () => {
    const node = buildSchemaOrgNode(
      entity({ description: { text: '', html: '', plain: '   ', citations: [] } }),
      info({ types: ['DefinedTerm'] }),
      PAGE,
    );
    expect(node).not.toHaveProperty('description');
  });
});

describe('buildEntityJsonLd', () => {
  it('emits a @graph of the entity node plus a Home › name breadcrumb', () => {
    const graph = buildEntityJsonLd(entity(), info({ types: ['DefinedTerm'] }), PAGE);
    expect(graph['@context']).toBe('https://schema.org');
    const nodes = graph['@graph'] as Record<string, unknown>[];
    expect(nodes).toHaveLength(2);

    expect(nodes[0]['@id']).toBe(`${ORIGIN}/themes/fantasy`);

    const crumb = nodes[1];
    expect(crumb['@type']).toBe('BreadcrumbList');
    const items = crumb.itemListElement as Record<string, unknown>[];
    expect(items.map((i) => i.name)).toEqual(['Home', 'Fantasy']);
    expect(items[0].item).toBe(`${ORIGIN}/`);
    expect(items[1].item).toBe(`${ORIGIN}/themes/fantasy`);
  });
});

describe('listingMeta', () => {
  it('defaults title, heading and breadcrumb to the plural label when no overrides are set', () => {
    expect(listingMeta('franchise')).toEqual({
      title: 'Franchises',
      heading: 'Franchises',
      breadcrumb: 'Franchises',
      description: franchise.listing?.description,
      itemLabel: 'franchise',
      itemLabelPlural: 'franchises',
    });
  });

  it('uses listing.title, with heading and breadcrumb defaulting to it when unset', () => {
    expect(listingMeta('theme')).toEqual({
      title: 'Pinball Machine Themes',
      heading: 'Pinball Machine Themes',
      breadcrumb: 'Pinball Machine Themes',
      description: theme.listing?.description,
      itemLabel: 'theme',
      itemLabelPlural: 'themes',
    });
  });

  it('the games listing resolves every label from its title', () => {
    // No entity currently overrides `heading`; if one returns, cover the
    // heading-independent-of-title branch with it here.
    expect(listingMeta('title')).toEqual({
      title: 'Games',
      heading: 'Games',
      breadcrumb: 'Games',
      description: title.listing?.description,
      itemLabel: 'game',
      itemLabelPlural: 'games',
    });
  });

  it('breadcrumb overrides the crumb independently of title and heading', () => {
    expect(listingMeta('person')).toEqual({
      title: 'Notable Pinball People',
      heading: 'Notable Pinball People',
      breadcrumb: 'Notable People',
      description: person.listing?.description,
      itemLabel: 'person',
      itemLabelPlural: 'people',
    });
  });
});

describe('buildListingJsonLd', () => {
  const items = [
    { slug: 'fantasy', name: 'Fantasy' },
    { slug: 'horror', name: 'Horror' },
  ];

  it('emits a CollectionPage whose mainEntity is a named ItemList, plus a breadcrumb', () => {
    const graph = buildListingJsonLd('theme', items, new URL(`${ORIGIN}/themes`), 137)[
      '@graph'
    ] as Record<string, unknown>[];
    expect(graph).toHaveLength(3);

    const [collection, itemList, crumb] = graph;
    expect(collection['@type']).toBe('CollectionPage');
    expect(collection['@id']).toBe(`${ORIGIN}/themes`);
    expect(collection.name).toBe('Pinball Machine Themes');
    expect(collection.description).toBe(theme.listing?.description);
    // CollectionPage links to the ItemList by @id, so they aren't orphaned.
    expect(collection.mainEntity).toEqual({ '@id': `${ORIGIN}/themes#items` });

    expect(itemList['@type']).toBe('ItemList');
    expect(itemList['@id']).toBe(`${ORIGIN}/themes#items`);
    // numberOfItems is the full collection size, not the page-1 sample length.
    expect(itemList.numberOfItems).toBe(137);
    const els = itemList.itemListElement as Record<string, unknown>[];
    expect(els.map((e) => e.position)).toEqual([1, 2]);
    expect(els.map((e) => e.item)).toEqual([
      { '@id': `${ORIGIN}/themes/fantasy`, name: 'Fantasy' },
      { '@id': `${ORIGIN}/themes/horror`, name: 'Horror' },
    ]);

    expect(crumb['@type']).toBe('BreadcrumbList');
    const citems = crumb.itemListElement as Record<string, unknown>[];
    expect(citems.map((i) => i.name)).toEqual(['Home', 'Pinball Machine Themes']);
  });

  it('numberOfItems defaults to the listed count when no total is given', () => {
    const graph = buildListingJsonLd('theme', items, new URL(`${ORIGIN}/themes`))[
      '@graph'
    ] as Record<string, unknown>[];
    expect(graph[1].numberOfItems).toBe(2);
  });

  it('omits the ItemList on a filtered/paginated URL (canonical to base)', () => {
    // The filtered subset must not be published under the bare-listing @id.
    const graph = buildListingJsonLd('theme', items, new URL(`${ORIGIN}/themes?q=foo&page=2`))[
      '@graph'
    ] as Record<string, unknown>[];
    expect(graph).toHaveLength(2);
    expect(graph.map((n) => n['@type'])).toEqual(['CollectionPage', 'BreadcrumbList']);
    expect(graph[0]['@id']).toBe(`${ORIGIN}/themes`);
    expect(graph[0].mainEntity).toBeUndefined();
  });
});

describe('fieldMap', () => {
  it('maps source fields to their schema.org property names', () => {
    const node = buildNode(
      { ...entity(), logo_url: 'https://cdn.example/logo.png', website: 'https://stern.example' },
      { types: ['Brand'], fieldMap: { logo_url: 'logo', website: 'url' } },
      'manufacturer',
    );
    expect(node.logo).toBe('https://cdn.example/logo.png');
    expect(node.url).toBe('https://stern.example');
  });

  it('null or empty source values are dropped', () => {
    const node = buildNode(
      { ...entity(), logo_url: null, website: '' },
      { types: ['Brand'], fieldMap: { logo_url: 'logo', website: 'url' } },
      'manufacturer',
    );
    expect(node).not.toHaveProperty('logo');
    expect(node).not.toHaveProperty('url');
  });

  it('transform "year" coerces an int year to a partial-ISO string', () => {
    const node = buildNode(
      { ...entity(), year: 1992 },
      { types: ['Game'], fieldMap: { year: { property: 'releaseDate', transform: 'year' } } },
      'model',
    );
    expect(node.releaseDate).toBe('1992');
  });

  it('a bare-string entry still copies the value as-is', () => {
    const node = buildNode(
      { ...entity(), hero_image_url: 'https://cdn.example/hero.png' },
      { types: ['Game'], fieldMap: { hero_image_url: 'image' } },
      'model',
    );
    expect(node.image).toBe('https://cdn.example/hero.png');
  });

  it('transform "year" still drops a null source value', () => {
    const node = buildNode(
      { ...entity(), year_start: null },
      {
        types: ['Organization'],
        fieldMap: { year_start: { property: 'foundingDate', transform: 'year' } },
      },
      'corporate-entity',
    );
    expect(node).not.toHaveProperty('foundingDate');
  });
});

describe('relationshipMap (single FK)', () => {
  it('emits a single @id ref using the target entity_type_plural', () => {
    const node = buildNode(
      { ...entity({ public_id: 'spike-2' }), manufacturer: { name: 'Stern', public_id: 'stern' } },
      { types: ['CreativeWork'], relationshipMap: { manufacturer: 'producer' } },
      'system',
    );
    // /manufacturers/, not /systems/ — the target's plural, not the subject's.
    expect(node.producer).toEqual({ '@id': `${ORIGIN}/manufacturers/stern` });
  });

  it('a null ref drops the property', () => {
    const node = buildNode(
      { ...entity(), manufacturer: null },
      { types: ['CreativeWork'], relationshipMap: { manufacturer: 'producer' } },
      'system',
    );
    expect(node).not.toHaveProperty('producer');
  });
});

describe('relationshipMap (many)', () => {
  it('emits an array of @id refs', () => {
    const node = buildNode(
      {
        ...entity(),
        parents: [
          { name: 'Solid State', public_id: 'solid-state' },
          { name: 'Electromechanical', public_id: 'em' },
        ],
      },
      { types: ['DefinedTerm'], relationshipMap: { parents: 'isPartOf' } },
      'theme',
    );
    expect(node.isPartOf).toEqual([
      { '@id': `${ORIGIN}/themes/solid-state` },
      { '@id': `${ORIGIN}/themes/em` },
    ]);
  });

  it('an empty list drops the property', () => {
    const node = buildNode(
      { ...entity(), parents: [] },
      { types: ['DefinedTerm'], relationshipMap: { parents: 'isPartOf' } },
      'theme',
    );
    expect(node).not.toHaveProperty('isPartOf');
  });
});

describe('relationshipMap guard', () => {
  it('mapping a non-relationship (scalar) field throws', () => {
    expect(() =>
      buildNode(
        { ...entity() },
        { types: ['DefinedTerm'], relationshipMap: { name: 'producer' } },
        'theme',
      ),
    ).toThrow(/not a declared relationship/);
  });
});

describe('per-model declarations', () => {
  it('theme is a DefinedTerm', () => {
    expect(theme.entityType).toBe('theme');
    expect(theme.schemaOrg.types).toEqual(['DefinedTerm']);
  });

  it('credit-role is an Occupation', () => {
    expect(creditRole.entityType).toBe('credit-role');
    expect(creditRole.schemaOrg.types).toEqual(['Occupation']);
  });

  it('manufacturer is a Brand with a logo/url fieldMap', () => {
    expect(manufacturer.entityType).toBe('manufacturer');
    expect(manufacturer.schemaOrg.types).toEqual(['Brand']);
    expect(manufacturer.schemaOrg.fieldMap).toEqual({ logo_url: 'logo', website: 'url' });
  });

  it('system is a CreativeWork mapping manufacturer → producer', () => {
    expect(system.entityType).toBe('system');
    expect(system.schemaOrg.types).toEqual(['CreativeWork']);
    expect(system.schemaOrg.relationshipMap).toEqual({ manufacturer: 'producer' });
  });

  it('theme maps parents → isPartOf', () => {
    expect(theme.schemaOrg.relationshipMap).toEqual({ parents: 'isPartOf' });
  });

  it('corporate-entity is an Organization mapping manufacturer → brand', () => {
    expect(corporateEntity.schemaOrg.types).toEqual(['Organization']);
    expect(corporateEntity.schemaOrg.fieldMap).toBeUndefined();
    expect(corporateEntity.schemaOrg.relationshipMap).toEqual({ manufacturer: 'brand' });
  });

  it('series and franchise are bare CreativeWork(Series) with no maps', () => {
    expect(series.schemaOrg.types).toEqual(['CreativeWorkSeries']);
    expect(series.schemaOrg.fieldMap).toBeUndefined();
    expect(franchise.schemaOrg.types).toEqual(['CreativeWork']);
    expect(franchise.schemaOrg.relationshipMap).toBeUndefined();
  });

  it('model is Game+ProductModel with releaseDate/image and FK refs', () => {
    expect(model.schemaOrg.types).toEqual(['Game', 'ProductModel']);
    expect(model.schemaOrg.fieldMap).toEqual({
      year: { property: 'releaseDate', transform: 'year' },
      hero_image_url: 'image',
    });
    expect(model.schemaOrg.relationshipMap).toEqual({
      corporate_entity: 'brand',
      title: 'exampleOfWork',
      themes: 'genre',
    });
  });

  it('title maps series/franchise to distinct properties (no key collision)', () => {
    expect(title.schemaOrg.types).toEqual(['Game']);
    expect(title.schemaOrg.relationshipMap).toEqual({
      series: 'isPartOf',
      franchise: 'isBasedOn',
    });
  });

  it('person maps birth/death years and photo', () => {
    expect(person.schemaOrg.types).toEqual(['Person']);
    expect(person.schemaOrg.fieldMap).toEqual({
      birth_year: { property: 'birthDate', transform: 'year' },
      death_year: { property: 'deathDate', transform: 'year' },
      photo_url: 'image',
    });
  });
});

describe('location per-row types', () => {
  const typesFor = (location_type: string | null) => {
    const fn = location.schemaOrg.types;
    if (typeof fn !== 'function') throw new Error('expected a function');
    return fn({ location_type } as unknown as LocationDetailSchema);
  };

  it('country/state/city map to their schema.org types', () => {
    expect(typesFor('country')).toEqual(['Country']);
    expect(typesFor('state')).toEqual(['State']);
    expect(typesFor('city')).toEqual(['City']);
  });

  it('both null and empty-string fall through to AdministrativeArea', () => {
    expect(typesFor(null)).toEqual(['AdministrativeArea']);
    expect(typesFor('')).toEqual(['AdministrativeArea']);
  });
});
