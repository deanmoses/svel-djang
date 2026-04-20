import { beforeEach, describe, expect, it, vi } from 'vitest';

import { savePersonClaims } from './save-person-claims';

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

describe('savePersonClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the people claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'jane' }, error: undefined });

		const result = await savePersonClaims('john', { fields: { name: 'Jane' } });

		expect(PATCH).toHaveBeenCalledWith('/api/people/{slug}/claims/', {
			params: { path: { slug: 'john' } },
			body: { fields: { name: 'Jane' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'jane' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await savePersonClaims('john', { fields: { name: 'John' } });

		expect(result).toEqual({ ok: true, updatedSlug: 'john' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { name: 'taken' }, form_errors: [] }
			}
		});

		const result = await savePersonClaims('john', { fields: { name: 'Jane' } });

		expect(result).toEqual({ ok: false, error: 'name: taken', fieldErrors: { name: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
