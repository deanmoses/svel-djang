import client from '$lib/api/client';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const { data, response } = await client.GET('/api/users/{username}/', {
		params: { path: { username: params.username } }
	});

	if (!data) {
		if (response?.status === 404) error(404, 'User not found');
		error(500, 'Failed to load user profile');
	}

	return { profile: data };
};
