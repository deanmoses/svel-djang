import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveThemeClaims } from './save-theme-claims';

const { PATCH, invalidateAll } = vi.hoisted(() => ({
	PATCH: vi.fn(),
	invalidateAll: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: { PATCH }
}));

vi.mock('$app/navigation', () => ({
	invalidateAll
}));

describe('saveThemeClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the themes claims endpoint with field changes', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'medieval' }, error: undefined });

		const result = await saveThemeClaims('medieval', {
			fields: { name: 'Medieval' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/themes/{slug}/claims/', {
			params: { path: { slug: 'medieval' } },
			body: { fields: { name: 'Medieval' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'medieval' });
	});

	it('PATCHes parents and aliases when supplied', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'medieval' }, error: undefined });

		await saveThemeClaims('medieval', {
			parents: ['fantasy'],
			aliases: ['Middle Ages'],
			note: 'rationale'
		});

		expect(PATCH).toHaveBeenCalledWith('/api/themes/{slug}/claims/', {
			params: { path: { slug: 'medieval' } },
			body: {
				fields: {},
				note: 'rationale',
				parents: ['fantasy'],
				aliases: ['Middle Ages']
			}
		});
	});

	it('returns the renamed slug when the response includes a new one', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'middle-ages' }, error: undefined });

		const result = await saveThemeClaims('medieval', {
			fields: { slug: 'middle-ages' }
		});

		expect(result).toEqual({ ok: true, updatedSlug: 'middle-ages' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveThemeClaims('medieval', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'medieval' });
	});

	it('returns parsed field errors on 422 and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: {
					message: 'invalid',
					field_errors: { parents: 'would create a cycle' },
					form_errors: []
				}
			}
		});

		const result = await saveThemeClaims('medieval', {
			parents: ['descendant-of-medieval']
		});

		expect(result).toEqual({
			ok: false,
			error: 'parents: would create a cycle',
			fieldErrors: { parents: 'would create a cycle' }
		});
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
