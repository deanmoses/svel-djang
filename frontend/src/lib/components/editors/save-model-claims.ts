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

/** Metadata that the modal passes through to an editor's save(). */
export type SaveMeta = {
	note?: string;
	citation?: components['schemas']['EditCitationInput'];
};

export type SaveResult = { ok: true } | { ok: false; error: string };

/** Extract a human-readable message from a Django Ninja error response. */
function formatApiError(error: unknown): string {
	if (typeof error === 'string') return error;
	if (typeof error === 'object' && error !== null && 'detail' in error) {
		const { detail } = error as { detail: unknown };
		if (typeof detail === 'string') return detail;
		// Pydantic validation: [{ loc: [...], msg: "..." }, ...]
		if (Array.isArray(detail)) {
			return detail
				.map((e) => {
					const loc = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '';
					return loc ? `${loc}: ${e.msg}` : e.msg;
				})
				.join('; ');
		}
	}
	return JSON.stringify(error);
}

/**
 * PATCH model claims and invalidate page data.
 * Returns `{ ok: true }` on success, or `{ ok: false, error }` on failure.
 */
export async function saveModelClaims(slug: string, body: SectionPatchBody): Promise<SaveResult> {
	const { error } = await client.PATCH('/api/models/{slug}/claims/', {
		params: { path: { slug } },
		body: { fields: {}, note: '', ...body }
	});

	if (error) {
		return { ok: false, error: formatApiError(error) };
	}

	await invalidateAll();
	return { ok: true };
}
