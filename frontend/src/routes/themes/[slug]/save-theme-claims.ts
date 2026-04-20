import { invalidateAll } from '$app/navigation';
import client from '$lib/api/client';
import {
	parseApiError,
	type FieldErrors,
	type SaveMeta,
	type SaveResult
} from '$lib/components/editors/save-claims-shared';
import type { HierarchicalTaxonomySectionPatchBody } from '$lib/components/editors/hierarchical-taxonomy-edit-types';

export { parseApiError };
export type { FieldErrors, SaveMeta, SaveResult };

export async function saveThemeClaims(
	slug: string,
	body: HierarchicalTaxonomySectionPatchBody
): Promise<SaveResult> {
	const { data, error } = await client.PATCH('/api/themes/{slug}/claims/', {
		params: { path: { slug } },
		body: { fields: {}, note: '', ...body }
	});

	if (error) {
		const parsed = parseApiError(error);
		return { ok: false, error: parsed.message, fieldErrors: parsed.fieldErrors };
	}

	await invalidateAll();
	return { ok: true, updatedSlug: data?.slug ?? slug };
}
