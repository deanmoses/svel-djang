import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveDisplayTypeClaims } from './save-display-type-claims';

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

describe('saveDisplayTypeClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the display-types claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'lcd' }, error: undefined });

		const result = await saveDisplayTypeClaims('liquid-crystal', {
			fields: { slug: 'lcd' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/display-types/{slug}/claims/', {
			params: { path: { slug: 'liquid-crystal' } },
			body: { fields: { slug: 'lcd' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'lcd' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveDisplayTypeClaims('lcd', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'lcd' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveDisplayTypeClaims('lcd', { fields: { slug: 'oled' } });

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
