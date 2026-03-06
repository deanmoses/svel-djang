import client from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const { data, response } = await client.GET('/api/titles/{slug}', {
		params: { path: { slug: params.slug } }
	});

	if (!data) {
		if (response?.status === 404) error(404, 'Title not found');
		error(500, 'Failed to load title');
	}

	return { title: data };
};
