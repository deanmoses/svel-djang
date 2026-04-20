import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveTechnologyGenerationClaims } from './save-technology-generation-claims';

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

describe('saveTechnologyGenerationClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the technology-generations claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'ss' }, error: undefined });

		const result = await saveTechnologyGenerationClaims('solid-state', {
			fields: { slug: 'ss' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/technology-generations/{slug}/claims/', {
			params: { path: { slug: 'solid-state' } },
			body: { fields: { slug: 'ss' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'ss' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveTechnologyGenerationClaims('ss', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'ss' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveTechnologyGenerationClaims('ss', { fields: { slug: 'other' } });

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
