import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ parent }) => {
	const { model } = await parent();

	// Single-model titles with no variants: redirect to the canonical title page.
	// Never redirect variant models — they have their own detail page.
	if (
		model.title_slug &&
		model.title_models.length === 1 &&
		model.title_models[0].variants.length === 0 &&
		!model.alias_of_slug
	) {
		redirect(301, `/titles/${model.title_slug}`);
	}
};
