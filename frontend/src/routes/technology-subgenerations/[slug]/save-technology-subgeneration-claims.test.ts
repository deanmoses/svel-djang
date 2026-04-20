import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveTechnologySubgenerationClaims } from './save-technology-subgeneration-claims';

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

describe('saveTechnologySubgenerationClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the technology-subgenerations claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'early-ss' }, error: undefined });

		const result = await saveTechnologySubgenerationClaims('early-solid-state', {
			fields: { slug: 'early-ss' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/technology-subgenerations/{slug}/claims/', {
			params: { path: { slug: 'early-solid-state' } },
			body: { fields: { slug: 'early-ss' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'early-ss' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveTechnologySubgenerationClaims('early-ss', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'early-ss' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveTechnologySubgenerationClaims('early-ss', {
			fields: { slug: 'other' }
		});

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
