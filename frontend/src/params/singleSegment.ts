import type { ParamMatcher } from '@sveltejs/kit';

// Rest params (`[...path]`) match zero or more URL segments, so without an
// explicit non-empty check they accept the empty string — which means
// `/themes/edit`, `/themes/edit-history`, etc. would silently match the
// migrated `[...path=singleSegment]/<subroute>` tree with `path === ''` and
// fire the layout loader against an empty slug. Reject empty here.
export const match: ParamMatcher = (param) => param.length > 0 && !param.includes('/');
