/**
 * Gating logic for the "Create?" prompt on the titles list page.
 *
 * Extracted so we can unit-test the invariant that the prompt is driven by
 * a query-only match set — not the faceted `filteredTitles` — and hidden
 * for anonymous users.
 */

import { emptyFilterState, filterTitles, type FacetedTitle } from '$lib/facet-engine';

export interface CreatePromptInputs {
	titles: FacetedTitle[];
	query: string;
	isAuthenticated: boolean;
}

export interface CreatePromptDecision {
	show: boolean;
	query: string;
}

export function decideCreatePrompt(inputs: CreatePromptInputs): CreatePromptDecision {
	const q = inputs.query.trim();
	if (!q) return { show: false, query: '' };
	if (!inputs.isAuthenticated) return { show: false, query: q };

	const queryOnlyMatches = filterTitles(inputs.titles, {
		...emptyFilterState(),
		query: q
	});
	return { show: queryOnlyMatches.length === 0, query: q };
}
