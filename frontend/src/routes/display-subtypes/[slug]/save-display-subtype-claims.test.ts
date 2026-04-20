import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveDisplaySubtypeClaims } from './save-display-subtype-claims';

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

describe('saveDisplaySubtypeClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the display-subtypes claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'alphanum' }, error: undefined });

		const result = await saveDisplaySubtypeClaims('alphanumeric', {
			fields: { slug: 'alphanum' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/display-subtypes/{slug}/claims/', {
			params: { path: { slug: 'alphanumeric' } },
			body: { fields: { slug: 'alphanum' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'alphanum' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveDisplaySubtypeClaims('alphanum', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'alphanum' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { slug: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveDisplaySubtypeClaims('alphanum', { fields: { slug: 'other' } });

		expect(result).toEqual({ ok: false, error: 'slug: taken', fieldErrors: { slug: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
