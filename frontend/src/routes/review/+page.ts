import client from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async () => {
	const { data } = await client.GET('/api/review/claims/');

	if (!data) {
		error(500, 'Failed to load review claims');
	}

	return { claims: data };
};
