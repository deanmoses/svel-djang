import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveGameFormatClaims } from './save-game-format-claims';

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

describe('saveGameFormatClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the game-formats claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'single-player' }, error: undefined });

		const result = await saveGameFormatClaims('singleplayer', {
			fields: { slug: 'single-player' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/game-formats/{slug}/claims/', {
			params: { path: { slug: 'singleplayer' } },
			body: { fields: { slug: 'single-player' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'single-player' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveGameFormatClaims('singleplayer', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'singleplayer' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveGameFormatClaims('singleplayer', { fields: { slug: 'other' } });

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
