/**
 * Shared save helper for section editors that PATCH title claims.
 */

import { invalidateAll } from '$app/navigation';
import client from '$lib/api/client';
import type { components } from '$lib/api/schema';
import { parseApiError, type SaveResult } from './save-claims-shared';

type TitleClaimsBody = components['schemas']['TitleClaimPatchSchema'];

export type TitleSectionPatchBody = Partial<
	Pick<TitleClaimsBody, 'fields' | 'abbreviations' | 'note' | 'citation'>
>;

export async function saveTitleClaims(
	slug: string,
	body: TitleSectionPatchBody
): Promise<SaveResult> {
	const { error } = await client.PATCH('/api/titles/{slug}/claims/', {
		params: { path: { slug } },
		body: { fields: {}, note: '', ...body }
	});

	if (error) {
		const parsed = parseApiError(error);
		return { ok: false, error: parsed.message, fieldErrors: parsed.fieldErrors };
	}

	await invalidateAll();
	return { ok: true };
}
