import type { components } from '$lib/api/schema';

export type LocationDetail = components['schemas']['LocationDetailSchema'];
export type LocationChild = components['schemas']['LocationChildRef'];

export const CHILD_TYPE_LABELS: Record<string, string> = {
  country: 'Countries',
  state: 'States',
  region: 'Regions',
  department: 'Departments',
  province: 'Provinces',
  community: 'Communities',
  prefecture: 'Prefectures',
  district: 'Districts',
  county: 'Counties',
  city: 'Cities',
};

export const CHILD_TYPE_SINGULAR: Record<string, string> = {
  country: 'Country',
  state: 'State',
  region: 'Region',
  department: 'Department',
  province: 'Province',
  community: 'Community',
  prefecture: 'Prefecture',
  district: 'District',
  county: 'County',
  city: 'City',
};

// Fallback when a parent has no children yet — pragmatic mapping of pindata's
// typical hierarchy. City has no expected child → "+ New …" hidden.
export const EXPECTED_CHILD: Record<string, string> = {
  country: 'State',
  state: 'City',
  region: 'City',
  province: 'City',
  department: 'City',
  community: 'City',
  prefecture: 'City',
  district: 'City',
  county: 'City',
};

export function childrenHeading(children: LocationChild[]): string {
  if (children.length === 0) return 'Subdivisions';
  const first = children[0].location_type;
  const allSame = children.every((c) => c.location_type === first);
  return allSame ? (CHILD_TYPE_LABELS[first] ?? 'Subdivisions') : 'Subdivisions';
}

export function newChildLabel(profile: LocationDetail): string | null {
  if (profile.children.length > 0) {
    return CHILD_TYPE_SINGULAR[profile.children[0].location_type] ?? null;
  }
  if (profile.location_type) {
    return EXPECTED_CHILD[profile.location_type] ?? null;
  }
  return null;
}
