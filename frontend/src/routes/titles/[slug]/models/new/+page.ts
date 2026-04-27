import { error, redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import client from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
  // Auth is server-authoritative; mirror the titles/new gate by bouncing
  // anonymous users to login before they fill out a form they cannot submit.
  const authRes = await fetch('/api/auth/me/');
  if (authRes.ok) {
    const auth = (await authRes.json()) as { is_authenticated?: boolean };
    if (!auth.is_authenticated) {
      throw redirect(302, resolve('/login'));
    }
  }

  // Load the parent title so the heading renders the real name ("Pokémon"
  // rather than the ASCII slug "pokemon"). We fetch directly here rather
  // than inheriting from the parent `[slug]/+layout.server.ts` because this
  // page escapes the parent layout via `+page@.svelte` — SvelteKit does not
  // inherit parent-layout data through a layout reset.
  const api = client;
  const { data, response } = await api.GET('/api/pages/title/{public_id}', {
    fetch,
    params: { path: { public_id: params.slug } },
  });
  if (!data) {
    if (response?.status === 404) throw error(404, 'Title not found');
    throw error(response.status || 500, 'Failed to load title');
  }
  return { title: { name: data.name, slug: data.slug } };
};
