import { error } from '@sveltejs/kit';
import { createServerClient } from '$lib/api/server';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ fetch, url, params }) => {
	const client = createServerClient(fetch, url);
	const { data, response } = await client.GET('/api/pages/cabinet/{slug}', {
		params: { path: { slug: params.slug } }
	});

	if (!data) {
		if (response?.status === 404) throw error(404, 'Cabinet not found');
		throw error(response.status || 500, 'Failed to load page');
	}

	return { profile: data };
};
