import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveManufacturerClaims } from './save-manufacturer-claims';

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

describe('saveManufacturerClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the manufacturers claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'bally' }, error: undefined });

		const result = await saveManufacturerClaims('williams', {
			fields: { name: 'Bally', slug: 'bally' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/manufacturers/{slug}/claims/', {
			params: { path: { slug: 'williams' } },
			body: { fields: { name: 'Bally', slug: 'bally' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'bally' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveManufacturerClaims('williams', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'williams' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveManufacturerClaims('williams', { fields: { slug: 'bally' } });

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
