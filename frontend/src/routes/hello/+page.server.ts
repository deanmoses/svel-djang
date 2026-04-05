import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import { createApiClient } from '$lib/api/client';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, url }) => {
	const apiBaseUrl = env.INTERNAL_API_BASE_URL?.trim() || url.origin;
	const client = createApiClient(fetch, apiBaseUrl);
	const { data, response } = await client.GET('/api/hello/');

	if (!data) {
		throw error(response.status || 500, 'Failed to load hello message');
	}

	return { message: data.message };
};
