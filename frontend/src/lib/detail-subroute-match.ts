/**
 * Returns the subroute segment of `/:entity/:slug/:subroute(/...)`,
 * or `null` when the pathname has fewer than three segments.
 *
 * Both `isFocusModePath` and `resolveDetailSubrouteMode` use this helper
 * so they cannot drift on the slug-guard rule: a detail page for a record
 * whose slug happens to be `sources`, `edit-history`, `edit`, etc. (e.g.
 * `/titles/sources`) must NOT classify as that subroute.
 */
export function matchDetailSubroute(pathname: string): string | null {
	const segments = pathname.split('/').filter(Boolean);
	if (segments.length < 3) return null;
	return segments[2];
}
