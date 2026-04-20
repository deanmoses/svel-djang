/**
 * Shared pure helpers for hierarchical entity display (Theme, GameplayFeature).
 */

/**
 * Normalize an alias for near-duplicate filtering against the canonical name.
 * Matches the backend's old `_normalize`: lowercase, strip hyphens/spaces, and
 * collapse a trailing 's' (so "pop-bumpers" and "Pop Bumper" collide).
 */
function normalizeAliasForFilter(s: string): string {
	let n = s.toLowerCase().replace(/-/g, '').replace(/ /g, '');
	if (n.endsWith('s')) n = n.slice(0, -1);
	return n;
}

/**
 * Filter aliases that are near-duplicates of the canonical name. Used by both
 * the desktop sidebar and the mobile meta bar so the "Also known as" affordance
 * never shows a value the user already sees in the heading.
 */
export function displayAliasesFor(name: string, aliases: string[]): string[] {
	const canonical = normalizeAliasForFilter(name);
	return aliases.filter((a) => normalizeAliasForFilter(a) !== canonical);
}
