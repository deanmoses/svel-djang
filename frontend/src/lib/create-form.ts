/**
 * Shared helpers for record-create pages (Title Create, Model Create, …).
 *
 * Extracted from the original title-create module once a second caller
 * appeared. All creation flows share the same slug-sync behavior and the
 * same response-classification shape, so there is no per-record version.
 *
 * What does not live here: record-type-specific slug auto-population (e.g.
 * Model's title-prefix rule), which belongs next to the record's Create
 * page. This module is intentionally agnostic about which record is being
 * created.
 */

import { parseApiError } from '$lib/components/editors/save-claims-shared';

/**
 * Lowercase, hyphen-separated slug derived from a catalog name.
 *
 * NFKD (not NFKC) is deliberate: we want decorative marks like ™ to
 * decompose to a base letter + mark so the mark can be stripped by the
 * non-alnum pass. The collision-check normalizer uses NFKC for a different
 * reason — see ``$lib/naming.ts``.
 */
export function slugifyForCatalog(raw: string): string {
	return raw
		.normalize('NFKD')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.replace(/-{2,}/g, '-');
}

/**
 * Given the new name value and the current form state, return the slug
 * that should be shown to the user.
 *
 * Sync auto-fills the slug from the name until the user diverges the slug.
 * Once diverged, the user's manual value is preserved — even if they later
 * edit the name.
 *
 * Consumers that need a non-identity projection from name → slug (e.g.
 * Model Create's title-prefix rule) should pass their projected value as
 * the ``projectedSlug`` argument. If omitted, `slugifyForCatalog(name)` is
 * used.
 */
export function reconcileSlug(opts: {
	name: string;
	slug: string;
	syncedSlug: string;
	projectedSlug?: string;
}): { slug: string; syncedSlug: string } {
	const next = opts.projectedSlug ?? slugifyForCatalog(opts.name);
	if (opts.slug === opts.syncedSlug && opts.slug !== next) {
		return { slug: next, syncedSlug: next };
	}
	return { slug: opts.slug, syncedSlug: opts.syncedSlug };
}

export type CreateOutcome<T extends { slug: string }> =
	| { kind: 'ok'; slug: string; data: T }
	| { kind: 'rate_limited'; retryAfterSeconds: number; message: string }
	| { kind: 'field_errors'; fieldErrors: Record<string, string>; message: string }
	| { kind: 'form_error'; message: string };

/**
 * Classify the result of a create POST into a shape the UI can render.
 * Keeps view components free of HTTP-shape knowledge.
 *
 * Generic over the created entity type — the only guarantee the caller
 * needs is that the response body has a ``slug`` string.
 */
export function classifyCreateResponse<T extends { slug: string }>(args: {
	data: T | undefined;
	error: unknown;
	response: { status: number; headers: Headers };
}): CreateOutcome<T> {
	if (args.response.status === 429) {
		const retryAfter = Number(args.response.headers.get('Retry-After') ?? '3600');
		const mins = Math.max(1, Math.ceil(retryAfter / 60));
		return {
			kind: 'rate_limited',
			retryAfterSeconds: retryAfter,
			message: `You've reached the create limit. Try again in about ${mins} minute${mins === 1 ? '' : 's'}.`
		};
	}

	if (args.error || !args.data) {
		const parsed = parseApiError(args.error);
		if (Object.keys(parsed.fieldErrors).length > 0) {
			return { kind: 'field_errors', fieldErrors: parsed.fieldErrors, message: parsed.message };
		}
		return { kind: 'form_error', message: parsed.message || 'Could not create record.' };
	}

	return { kind: 'ok', slug: args.data.slug, data: args.data };
}
