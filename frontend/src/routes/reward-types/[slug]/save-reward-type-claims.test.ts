import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveRewardTypeClaims } from './save-reward-type-claims';

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

describe('saveRewardTypeClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the reward-types claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'free-game' }, error: undefined });

		const result = await saveRewardTypeClaims('freegame', {
			fields: { slug: 'free-game' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/reward-types/{slug}/claims/', {
			params: { path: { slug: 'freegame' } },
			body: { fields: { slug: 'free-game' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'free-game' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveRewardTypeClaims('freegame', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'freegame' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveRewardTypeClaims('freegame', { fields: { slug: 'other' } });

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
