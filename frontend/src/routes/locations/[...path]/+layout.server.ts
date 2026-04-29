import { error } from '@sveltejs/kit';
import { createServerClient } from '$lib/api/server';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ fetch, url, params }) => {
  const path = params.path ?? '';
  const client = createServerClient(fetch, url);

  // Two routes: ``/`` for the global root, ``/{location_path}`` for any
  // concrete location. The path converter accepts slashes, so a single
  // typed call covers all depths.
  const result =
    path === ''
      ? await client.GET('/api/pages/locations/', {})
      : await client.GET('/api/pages/locations/{location_path}', {
          params: { path: { location_path: path } },
        });

  if (!result.data) {
    if (result.response?.status === 404) throw error(404, 'Location not found');
    throw error(result.response?.status || 500, 'Failed to load location');
  }

  return { profile: result.data };
};
