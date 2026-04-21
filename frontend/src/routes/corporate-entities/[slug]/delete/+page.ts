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

	// The preview already carries parent_name / parent_slug because the CE
	// registrar was wired with parent_field="manufacturer" — no separate
	// detail fetch needed.
	const res = await fetch(`/api/corporate-entities/${params.slug}/delete-preview/`);
	if (res.status === 404) {
		throw redirect(302, resolve('/corporate-entities'));
	}
	if (!res.ok) {
		throw new Error(`Failed to load delete preview (${res.status})`);
	}

	const preview = (await res.json()) as DeletePreview;
	return { preview, slug: params.slug };
};
