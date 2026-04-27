import { error, redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import client from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params, url }) => {
  const authRes = await fetch('/api/auth/me/');
  if (authRes.ok) {
    const data = (await authRes.json()) as { is_authenticated?: boolean };
    if (!data.is_authenticated) {
      throw redirect(302, resolve('/login'));
    }
  }

  // Load the parent manufacturer directly — this page escapes the parent
  // layout via `+page@.svelte`, so parent-layout data is not inherited.
  const { data, response } = await client.GET('/api/pages/manufacturer/{public_id}', {
    fetch,
    params: { path: { public_id: params.slug } },
  });
  if (!data) {
    if (response?.status === 404) throw error(404, 'Manufacturer not found');
    throw error(response.status || 500, 'Failed to load manufacturer');
  }

  return {
    manufacturer: { name: data.name, slug: data.slug },
    initialName: url.searchParams.get('name') ?? '',
  };
};
