/**
 * Pure helpers for the Title Create page.
 *
 * The UI state in +page.svelte is thin; these helpers carry the logic that's
 * worth testing without mounting the component: slug generation, name/slug
 * sync decisions, and response classification.
 */

import type { components } from '$lib/api/schema';

import { parseApiError } from '$lib/components/editors/save-claims-shared';

export function slugifyForTitle(raw: string): string {
	// NFKD (not NFKC) is deliberate: we want decorative marks like ™ to
	// decompose to a base letter + mark so the mark can be stripped by the
	// non-alnum pass. The collision-check normalizer uses NFKC for a
	// different reason — see naming.ts.
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
 */
export function reconcileSlug(opts: { name: string; slug: string; syncedSlug: string }): {
	slug: string;
	syncedSlug: string;
} {
	const next = slugifyForTitle(opts.name);
	if (opts.slug === opts.syncedSlug && opts.slug !== next) {
		return { slug: next, syncedSlug: next };
	}
	return { slug: opts.slug, syncedSlug: opts.syncedSlug };
}

export type CreateOutcome =
	| { kind: 'ok'; slug: string }
	| { kind: 'rate_limited'; retryAfterSeconds: number; message: string }
	| { kind: 'field_errors'; fieldErrors: Record<string, string>; message: string }
	| { kind: 'form_error'; message: string };

/**
 * Classify the result of a POST /api/titles/ call into a shape the UI can
 * render. Keeps the view component free of HTTP-shape knowledge.
 */
export function classifyCreateResponse(args: {
	data: components['schemas']['TitleDetailSchema'] | undefined;
	error: unknown;
	response: { status: number; headers: Headers };
}): CreateOutcome {
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
		return { kind: 'form_error', message: parsed.message || 'Could not create title.' };
	}

	return { kind: 'ok', slug: args.data.slug };
}
