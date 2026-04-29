import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
  const res = await fetch('/api/auth/me/');
  if (res.ok) {
    const data = (await res.json()) as { is_authenticated?: boolean };
    if (!data.is_authenticated) {
      throw redirect(302, resolve('/login'));
    }
  }

  return {
    initialName: url.searchParams.get('name') ?? '',
  };
};
