/**
 * Shared loader for per-entity edit-history routes. Every
 * `<entity>/[slug]/edit-history/+page.server.ts` is the same call to
 * `/api/edit-history/{entity_type}/{slug}/` with one varying string.
 */
import { error } from '@sveltejs/kit';
import { createServerClient } from '$lib/api/server';
import type { CatalogEntityKey } from '$lib/api/catalog-meta';

type LoadEvent = {
	fetch: typeof fetch;
	url: URL;
};

export async function loadEditHistory(
	event: LoadEvent,
	entityType: CatalogEntityKey,
	slug: string
) {
	const client = createServerClient(event.fetch, event.url);
	const { data, response } = await client.GET('/api/edit-history/{entity_type}/{slug}/', {
		params: { path: { entity_type: entityType, slug } }
	});

	if (!data) {
		throw error(response.status || 500, 'Failed to load edit history');
	}

	return { changesets: data, entityType, slug };
}
