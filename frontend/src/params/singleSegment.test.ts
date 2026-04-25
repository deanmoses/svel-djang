import { describe, it, expect } from 'vitest';
import { match } from './singleSegment';

describe('singleSegment param matcher', () => {
  it('accepts a single non-empty segment', () => {
    expect(match('sports')).toBe(true);
    expect(match('sci-fi')).toBe(true);
    expect(match('a')).toBe(true);
  });

  it('rejects the empty string', () => {
    // Rest params match zero segments by default, which would let
    // `/themes/edit`, `/themes/edit-history`, `/themes/sources`, etc. silently
    // match the migrated `[...path=singleSegment]/<subroute>` tree with
    // path === '' and fire layout loaders against an empty slug.
    expect(match('')).toBe(false);
  });

  it('rejects multi-segment paths', () => {
    expect(match('foo/bar')).toBe(false);
    expect(match('a/b/c')).toBe(false);
  });
});
