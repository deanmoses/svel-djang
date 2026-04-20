import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveCabinetClaims } from './save-cabinet-claims';

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

describe('saveCabinetClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the cabinets claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'widebody' }, error: undefined });

		const result = await saveCabinetClaims('wide-body', {
			fields: { slug: 'widebody' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/cabinets/{slug}/claims/', {
			params: { path: { slug: 'wide-body' } },
			body: { fields: { slug: 'widebody' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'widebody' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveCabinetClaims('widebody', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'widebody' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveCabinetClaims('widebody', { fields: { slug: 'other' } });

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
