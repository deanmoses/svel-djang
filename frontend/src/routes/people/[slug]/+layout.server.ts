import { error } from '@sveltejs/kit';
import { createServerClient } from '$lib/api/server';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ fetch, url, params }) => {
  const client = createServerClient(fetch, url);
  const { data, response } = await client.GET('/api/pages/person/{public_id}', {
    params: { path: { public_id: params.slug } },
  });

  if (!data) {
    if (response?.status === 404) throw error(404, 'Person not found');
    throw error(response.status || 500, 'Failed to load page');
  }

  return { person: data };
};
