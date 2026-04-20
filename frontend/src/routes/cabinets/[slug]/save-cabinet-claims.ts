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

type CabinetClaimsBody = components['schemas']['ClaimPatchSchema'];

export type CabinetSectionPatchBody = Partial<
	Pick<CabinetClaimsBody, 'fields' | 'note' | 'citation'>
>;

export async function saveCabinetClaims(
	slug: string,
	body: CabinetSectionPatchBody
): Promise<SaveResult> {
	const { data, error } = await client.PATCH('/api/cabinets/{slug}/claims/', {
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
