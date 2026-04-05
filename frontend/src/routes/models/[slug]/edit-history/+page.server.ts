import { error } from '@sveltejs/kit';
import { createServerClient } from '$lib/api/server';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, url, params }) => {
	const client = createServerClient(fetch, url);
	const { data, response } = await client.GET('/api/edit-history/{entity_type}/{slug}/', {
		params: { path: { entity_type: 'machinemodel', slug: params.slug } }
	});

	if (!data) {
		throw error(response.status || 500, 'Failed to load edit history');
	}

	return { changesets: data, entityType: 'machinemodel', slug: params.slug };
};
