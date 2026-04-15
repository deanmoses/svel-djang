/**
 * Shared save helper for section editors that PATCH model claims.
 *
 * Each section editor builds a `fields` object with only the changed
 * scalar values, then calls this function. It handles the API call,
 * error formatting, and page data invalidation.
 */

import { invalidateAll } from '$app/navigation';
import client from '$lib/api/client';

export type SaveResult = { ok: true } | { ok: false; error: string };

/**
 * PATCH changed fields to the model claims endpoint.
 * Returns `{ ok: true }` on success, or `{ ok: false, error }` on failure.
 * Calls `invalidateAll()` on success so the page reflects the update.
 */
export async function saveModelFields(
	slug: string,
	fields: Record<string, unknown>
): Promise<SaveResult> {
	const { error } = await client.PATCH('/api/models/{slug}/claims/', {
		params: { path: { slug } },
		body: { fields, note: '' }
	});

	if (error) {
		const message = typeof error === 'string' ? error : JSON.stringify(error);
		return { ok: false, error: message };
	}

	await invalidateAll();
	return { ok: true };
}
