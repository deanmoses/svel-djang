import { describe, expect, it } from 'vitest';
import {
  childrenHeading,
  newChildLabel,
  type LocationChild,
  type LocationDetail,
} from './location-helpers';

function child(name: string, type: string): LocationChild {
  return {
    name,
    slug: name.toLowerCase(),
    location_path: name.toLowerCase(),
    location_type: type,
    manufacturer_count: 0,
  };
}

function profile(overrides: Partial<LocationDetail>): LocationDetail {
  return {
    name: '',
    slug: '',
    location_path: '',
    location_type: null,
    manufacturer_count: 0,
    ancestors: [],
    children: [],
    manufacturers: [],
    ...overrides,
  };
}

describe('childrenHeading', () => {
  it('returns the plural label when all children share a type', () => {
    expect(childrenHeading([child('USA', 'country'), child('NL', 'country')])).toBe('Countries');
    expect(childrenHeading([child('IL', 'state'), child('TX', 'state')])).toBe('States');
  });

  it('falls back to "Subdivisions" when children are mixed types', () => {
    // UK-style: countries-within-country plus regions
    expect(childrenHeading([child('England', 'country'), child('NorthernRegion', 'region')])).toBe(
      'Subdivisions',
    );
  });

  it('falls back to "Subdivisions" for an unknown type', () => {
    expect(childrenHeading([child('X', 'oblast')])).toBe('Subdivisions');
  });

  it('returns "Subdivisions" for an empty list', () => {
    expect(childrenHeading([])).toBe('Subdivisions');
  });
});

describe('newChildLabel', () => {
  it('uses the singular form of the existing children type', () => {
    expect(
      newChildLabel(profile({ location_type: 'country', children: [child('IL', 'state')] })),
    ).toBe('State');
  });

  it('falls back to EXPECTED_CHILD when there are no children yet', () => {
    expect(newChildLabel(profile({ location_type: 'country' }))).toBe('State');
    expect(newChildLabel(profile({ location_type: 'state' }))).toBe('City');
  });

  it('returns null for a city (no expected child)', () => {
    expect(newChildLabel(profile({ location_type: 'city' }))).toBeNull();
  });

  it('returns null at the root (no location_type) when no children', () => {
    expect(newChildLabel(profile({ location_type: null }))).toBeNull();
  });

  it('uses children type even at root when children exist', () => {
    expect(
      newChildLabel(profile({ location_type: null, children: [child('USA', 'country')] })),
    ).toBe('Country');
  });
});
