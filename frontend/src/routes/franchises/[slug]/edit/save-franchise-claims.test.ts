import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveFranchiseClaims } from './save-franchise-claims';

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

describe('saveFranchiseClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the franchises claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'star-wars' }, error: undefined });

		const result = await saveFranchiseClaims('starwars', { fields: { slug: 'star-wars' } });

		expect(PATCH).toHaveBeenCalledWith('/api/franchises/{slug}/claims/', {
			params: { path: { slug: 'starwars' } },
			body: { fields: { slug: 'star-wars' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'star-wars' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveFranchiseClaims('starwars', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'starwars' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { name: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveFranchiseClaims('starwars', { fields: { name: 'Star Wars' } });

		expect(result).toEqual({ ok: false, error: 'name: taken', fieldErrors: { name: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
