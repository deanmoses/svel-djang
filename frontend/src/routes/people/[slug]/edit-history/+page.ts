import client from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const { data } = await client.GET('/api/edit-history/{entity_type}/{slug}/', {
		params: { path: { entity_type: 'person', slug: params.slug } }
	});

	if (!data) error(500, 'Failed to load edit history');

	return { changesets: data };
};
