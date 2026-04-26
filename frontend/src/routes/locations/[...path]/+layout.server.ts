import { error } from '@sveltejs/kit';
import { createServerClient } from '$lib/api/server';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ fetch, url, params }) => {
  const segs = (params.path ?? '').split('/').filter(Boolean);
  if (segs.length > 4) throw error(404, 'Location not found');

  const client = createServerClient(fetch, url);

  // Ninja generates one OpenAPI path per explicit segment-count route, so we
  // dispatch on segment count to the matching typed call.
  const result =
    segs.length === 0
      ? await client.GET('/api/pages/locations/', {})
      : segs.length === 1
        ? await client.GET('/api/pages/locations/{s1}', {
            params: { path: { s1: segs[0] } },
          })
        : segs.length === 2
          ? await client.GET('/api/pages/locations/{s1}/{s2}', {
              params: { path: { s1: segs[0], s2: segs[1] } },
            })
          : segs.length === 3
            ? await client.GET('/api/pages/locations/{s1}/{s2}/{s3}', {
                params: { path: { s1: segs[0], s2: segs[1], s3: segs[2] } },
              })
            : await client.GET('/api/pages/locations/{s1}/{s2}/{s3}/{s4}', {
                params: { path: { s1: segs[0], s2: segs[1], s3: segs[2], s4: segs[3] } },
              });

  if (!result.data) {
    if (result.response?.status === 404) throw error(404, 'Location not found');
    throw error(result.response?.status || 500, 'Failed to load location');
  }

  return { profile: result.data };
};
