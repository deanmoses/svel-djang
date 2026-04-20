/**
 * Shared save helper for section editors that PATCH model claims.
 *
 * Each section editor builds a body with changed fields and/or
 * relationship data, then calls this function. It handles the API call,
 * error formatting, and page data invalidation.
 */

import { invalidateAll } from '$app/navigation';
import client from '$lib/api/client';
import type { components } from '$lib/api/schema';
import {
	parseApiError,
	type FieldErrors,
	type SaveMeta,
	type SaveResult
} from './save-claims-shared';

export { parseApiError };
export type { FieldErrors, SaveMeta, SaveResult };

type ModelClaimsBody = components['schemas']['ModelClaimPatchSchema'];

/**
 * Body keys that section editors may include in a PATCH.
 * `fields` and `note` default to `{}` and `''` respectively;
 * callers only supply keys they need.
 */
export type SectionPatchBody = Partial<
	Pick<
		ModelClaimsBody,
		| 'fields'
		| 'themes'
		| 'tags'
		| 'reward_types'
		| 'gameplay_features'
		| 'credits'
		| 'abbreviations'
		| 'note'
		| 'citation'
	>
>;

/**
 * PATCH model claims and invalidate page data.
 * Returns `{ ok: true }` on success, or `{ ok: false, error, fieldErrors }` on failure.
 */
export async function saveModelClaims(slug: string, body: SectionPatchBody): Promise<SaveResult> {
	const { error } = await client.PATCH('/api/models/{slug}/claims/', {
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
