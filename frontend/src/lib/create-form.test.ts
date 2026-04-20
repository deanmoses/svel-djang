import { describe, expect, it } from 'vitest';

import { classifyCreateResponse, reconcileSlug, slugifyForCatalog } from './create-form';

describe('slugifyForCatalog', () => {
	it('produces a lowercase-hyphenated slug', () => {
		expect(slugifyForCatalog('Godzilla')).toBe('godzilla');
		expect(slugifyForCatalog('Attack from Mars')).toBe('attack-from-mars');
	});

	it('collapses punctuation and runs of hyphens', () => {
		expect(slugifyForCatalog('Spider-Man 2!!!')).toBe('spider-man-2');
		expect(slugifyForCatalog('---Godzilla---')).toBe('godzilla');
	});

	it('returns the empty string for names with no alphanumerics', () => {
		expect(slugifyForCatalog('!!!')).toBe('');
		expect(slugifyForCatalog('   ')).toBe('');
	});

	it('preserves numbers', () => {
		expect(slugifyForCatalog('T2 Judgment Day')).toBe('t2-judgment-day');
	});
});

describe('reconcileSlug', () => {
	it('auto-fills the slug while the user has not diverged it', () => {
		const next = reconcileSlug({ name: 'Godzilla', slug: '', syncedSlug: '' });
		expect(next).toEqual({ slug: 'godzilla', syncedSlug: 'godzilla' });
	});

	it('keeps following the name until the user edits the slug', () => {
		let state = { slug: '', syncedSlug: '' };
		state = reconcileSlug({ name: 'Godzilla', ...state });
		expect(state.slug).toBe('godzilla');

		state = reconcileSlug({ name: 'Godzilla 2', ...state });
		expect(state.slug).toBe('godzilla-2');
	});

	it('stops syncing once the user diverges the slug', () => {
		let state = reconcileSlug({ name: 'Godzilla', slug: '', syncedSlug: '' });
		state = { slug: 'god', syncedSlug: state.syncedSlug };
		const next = reconcileSlug({ name: 'Godzilla 2', ...state });
		expect(next.slug).toBe('god');
		expect(next.syncedSlug).toBe('godzilla');
	});

	it('resumes syncing if the user clears their manual slug to match synced', () => {
		const afterReset = reconcileSlug({
			name: 'Attack',
			slug: 'attack',
			syncedSlug: 'attack'
		});
		const afterRename = reconcileSlug({
			name: 'Attack 2',
			slug: afterReset.slug,
			syncedSlug: afterReset.syncedSlug
		});
		expect(afterRename.slug).toBe('attack-2');
	});

	it('is a no-op when the slugified name equals the current slug', () => {
		const next = reconcileSlug({
			name: 'Godzilla',
			slug: 'godzilla',
			syncedSlug: 'godzilla'
		});
		expect(next).toEqual({ slug: 'godzilla', syncedSlug: 'godzilla' });
	});

	it('accepts a projectedSlug to override the default slugify rule', () => {
		// Example: Model Create passes a title-prefixed projection.
		const next = reconcileSlug({
			name: 'Pro',
			slug: '',
			syncedSlug: '',
			projectedSlug: 'godzilla-pro'
		});
		expect(next).toEqual({ slug: 'godzilla-pro', syncedSlug: 'godzilla-pro' });
	});
});

function resp(status: number, retryAfter?: string): { status: number; headers: Headers } {
	const h = new Headers();
	if (retryAfter !== undefined) h.set('Retry-After', retryAfter);
	return { status, headers: h };
}

describe('classifyCreateResponse', () => {
	it('returns ok with the new slug on success', () => {
		const outcome = classifyCreateResponse({
			data: { slug: 'godzilla', name: 'Godzilla' },
			error: undefined,
			response: resp(200)
		});
		expect(outcome.kind).toBe('ok');
		if (outcome.kind !== 'ok') throw new Error('type narrow');
		expect(outcome.slug).toBe('godzilla');
		expect(outcome.data.slug).toBe('godzilla');
	});

	it('returns rate_limited with a friendly message for 429', () => {
		const outcome = classifyCreateResponse({
			data: undefined,
			error: { detail: { message: 'Rate limit exceeded.' } },
			response: resp(429, '1800')
		});
		expect(outcome.kind).toBe('rate_limited');
		if (outcome.kind !== 'rate_limited') throw new Error('type narrow');
		expect(outcome.retryAfterSeconds).toBe(1800);
		expect(outcome.message).toMatch(/30 minutes/);
	});

	it('falls back to one hour when Retry-After is missing on 429', () => {
		const outcome = classifyCreateResponse({
			data: undefined,
			error: {},
			response: resp(429)
		});
		expect(outcome.kind).toBe('rate_limited');
		if (outcome.kind !== 'rate_limited') throw new Error('type narrow');
		expect(outcome.retryAfterSeconds).toBe(3600);
	});

	it('reports a field_errors outcome for 422 name collisions', () => {
		const outcome = classifyCreateResponse({
			data: undefined,
			error: {
				detail: {
					message: 'Name collision.',
					field_errors: { name: "A title named 'Godzilla' already exists." },
					form_errors: []
				}
			},
			response: resp(422)
		});
		expect(outcome.kind).toBe('field_errors');
		if (outcome.kind !== 'field_errors') throw new Error('type narrow');
		expect(outcome.fieldErrors.name).toMatch(/already exists/);
	});

	it('reports a field_errors outcome for 422 slug collisions', () => {
		const outcome = classifyCreateResponse({
			data: undefined,
			error: {
				detail: {
					message: 'Slug collision.',
					field_errors: { slug: "The slug 'godzilla' is already taken." },
					form_errors: []
				}
			},
			response: resp(422)
		});
		if (outcome.kind !== 'field_errors') throw new Error('type narrow');
		expect(outcome.fieldErrors.slug).toMatch(/already taken/);
	});

	it('reports a form_error outcome when only form-level errors are present', () => {
		const outcome = classifyCreateResponse({
			data: undefined,
			error: {
				detail: {
					message: 'No changes provided.',
					field_errors: {},
					form_errors: ['No changes provided.']
				}
			},
			response: resp(422)
		});
		expect(outcome.kind).toBe('form_error');
		if (outcome.kind !== 'form_error') throw new Error('type narrow');
		expect(outcome.message).toMatch(/No changes provided/);
	});
});
