import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import type { components } from '$lib/api/schema';
import type { PageLoad } from './$types';

export type DeletePreview = components['schemas']['TaxonomyDeletePreviewSchema'];

export const load: PageLoad = async ({ fetch, params }) => {
	const authRes = await fetch('/api/auth/me/');
	if (authRes.ok) {
		const data = (await authRes.json()) as { is_authenticated?: boolean };
		if (!data.is_authenticated) {
			throw redirect(302, resolve('/login'));
		}
	}

	const res = await fetch(`/api/systems/${params.slug}/delete-preview/`);
	if (res.status === 404) {
		throw redirect(302, resolve('/systems'));
	}
	if (!res.ok) {
		throw new Error(`Failed to load delete preview (${res.status})`);
	}

	const preview = (await res.json()) as DeletePreview;
	return { preview, slug: params.slug };
};
