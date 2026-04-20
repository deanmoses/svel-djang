import { invalidateAll } from '$app/navigation';
import client from '$lib/api/client';
import type { components } from '$lib/api/schema';
import {
	parseApiError,
	type FieldErrors,
	type SaveMeta,
	type SaveResult
} from '$lib/components/editors/save-claims-shared';

export { parseApiError };
export type { FieldErrors, SaveMeta, SaveResult };

type TechnologyGenerationClaimsBody = components['schemas']['ClaimPatchSchema'];

export type TechnologyGenerationSectionPatchBody = Partial<
	Pick<TechnologyGenerationClaimsBody, 'fields' | 'note' | 'citation'>
>;

export async function saveTechnologyGenerationClaims(
	slug: string,
	body: TechnologyGenerationSectionPatchBody
): Promise<SaveResult> {
	const { data, error } = await client.PATCH('/api/technology-generations/{slug}/claims/', {
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
