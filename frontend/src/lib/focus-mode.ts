import { matchDetailSubroute } from './detail-subroute-match';

/**
 * Focus-mode routes render their own minimal chrome (no site Nav/Footer or
 * page-content wrapper). Patterns:
 *   /:entity/new                         create a top-level record
 *   /:entity/:slug/:child/new            create a nested record
 *   /:entity/:slug/edit                  edit (no section)
 *   /:entity/:slug/edit/:section         edit a section
 *   /:entity/:slug/delete                destructive confirmation
 *   /:entity/:slug/edit-history          audit: changeset history
 *   /:entity/:slug/sources               audit: source claims
 *
 * `edit`, `delete`, `edit-history`, and `sources` require a slug segment
 * before them so a catalog record with slug='edit' / 'sources' / etc. (e.g.
 * /titles/sources) still gets full chrome. Slug-guard matching is delegated
 * to `matchDetailSubroute` so this stays in sync with `resolveDetailSubrouteMode`.
 *
 * `new` is safe without that guard because SvelteKit's route priority gives
 * /:entity/new to the create page, not the detail page.
 */
const FOCUS_SUBROUTES_NESTED = new Set(['edit']);
const FOCUS_SUBROUTES_TERMINAL = new Set(['delete', 'edit-history', 'sources']);

export function isFocusModePath(pathname: string): boolean {
	const segments = pathname.split('/').filter(Boolean);
	if (segments.length === 0) return false;

	if (segments[segments.length - 1] === 'new') return true;

	const subroute = matchDetailSubroute(pathname);
	if (!subroute) return false;

	if (FOCUS_SUBROUTES_NESTED.has(subroute)) return true;
	if (FOCUS_SUBROUTES_TERMINAL.has(subroute) && segments.length === 3) return true;

	return false;
}
