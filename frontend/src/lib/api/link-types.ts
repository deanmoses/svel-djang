/**
 * API client for wikilink autocomplete endpoints.
 *
 * Separate from the openapi-fetch client because these endpoints have
 * a simple, stable contract and don't need generated types.
 */

export type LinkType = {
	name: string;
	label: string;
	description: string;
	flow: 'standard' | 'custom';
};

export type LinkTarget = {
	ref: string;
	label: string;
};

type LinkTargetsResponse = {
	results: LinkTarget[];
};

// Module-level cache — link types don't change at runtime.
let cachedTypes: LinkType[] | null = null;

/** Reset cache — for tests only. */
export function _resetCache(): void {
	cachedTypes = null;
}

export async function fetchLinkTypes(): Promise<LinkType[]> {
	if (cachedTypes) return cachedTypes;

	const resp = await fetch('/api/link-types/');
	if (!resp.ok) throw new Error(`Failed to fetch link types: ${resp.status}`);

	cachedTypes = (await resp.json()) as LinkType[];
	return cachedTypes;
}

export async function searchLinkTargets(type: string, query: string): Promise<LinkTargetsResponse> {
	const params = new URLSearchParams({ type, q: query });
	const resp = await fetch(`/api/link-types/targets/?${params}`);
	if (!resp.ok) throw new Error(`Failed to search link targets: ${resp.status}`);

	return (await resp.json()) as LinkTargetsResponse;
}
