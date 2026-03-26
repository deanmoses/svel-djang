import client from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';

export const prerender = false;
export const ssr = false;

export const load: LayoutLoad = async ({ params }) => {
	const { data, response } = await client.GET('/api/themes/{slug}', {
		params: { path: { slug: params.slug } }
	});

	if (!data) {
		if (response?.status === 404) error(404, 'Theme not found');
		error(500, 'Failed to load theme');
	}

	return { theme: data };
};
