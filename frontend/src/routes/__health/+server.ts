import { env } from '$env/dynamic/private';
import { json } from '@sveltejs/kit';
import { createApiClient } from '$lib/api/client';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch, url }) => {
	const apiBaseUrl = env.INTERNAL_API_BASE_URL?.trim() || url.origin;
	const client = createApiClient(fetch, apiBaseUrl);
	const { data, response } = await client.GET('/api/health');

	if (!data || response.status !== 200) {
		return json({ status: 'error' }, { status: response.status || 500 });
	}

	return json(data);
};
