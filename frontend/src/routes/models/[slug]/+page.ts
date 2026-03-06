import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ parent }) => {
	const { model } = await parent();

	// Single-model titles: redirect to the canonical title page.
	if (model.title_slug && model.title_models.length === 0) {
		redirect(301, `/titles/${model.title_slug}`);
	}
};
