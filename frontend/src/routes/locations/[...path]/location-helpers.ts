import type { LocationChildRef, LocationDetailSchema } from '$lib/api/schema';

export type LocationDetail = LocationDetailSchema;
export type LocationChild = LocationChildRef;

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

export function childrenHeading(children: LocationChild[]): string {
  if (children.length === 0) return 'Subdivisions';
  const first = children[0].location_type;
  const allSame = children.every((c) => c.location_type === first);
  return allSame ? (CHILD_TYPE_LABELS[first] ?? 'Subdivisions') : 'Subdivisions';
}

export function newChildLabel(profile: LocationDetail): string | null {
  // Existing children are the most reliable signal — whatever type they
  // are is what a new sibling will be.
  if (profile.children.length > 0) {
    return CHILD_TYPE_SINGULAR[profile.children[0].location_type] ?? null;
  }
  // No children: trust the backend's server-derived label, which reads
  // from the country ancestor's ``divisions`` list. ``null`` means
  // divisions are missing or exhausted; the caller suppresses the
  // "+ New …" action rather than guess at a wrong label.
  if (profile.expected_child_type) {
    return CHILD_TYPE_SINGULAR[profile.expected_child_type] ?? null;
  }
  return null;
}
