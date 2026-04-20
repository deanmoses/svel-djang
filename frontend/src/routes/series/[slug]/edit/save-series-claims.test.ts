import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveSeriesClaims } from './save-series-claims';

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

describe('saveSeriesClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the series claims endpoint with the supplied body', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'system-11' }, error: undefined });

		const result = await saveSeriesClaims('system-11-old', { fields: { slug: 'system-11' } });

		expect(PATCH).toHaveBeenCalledWith('/api/series/{slug}/claims/', {
			params: { path: { slug: 'system-11-old' } },
			body: { fields: { slug: 'system-11' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'system-11' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveSeriesClaims('system-11', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'system-11' });
	});

	it('returns a parsed error on failure and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: { message: 'nope', field_errors: { name: 'taken' }, form_errors: [] }
			}
		});

		const result = await saveSeriesClaims('system-11', { fields: { name: 'System 11' } });

		expect(result).toEqual({ ok: false, error: 'name: taken', fieldErrors: { name: 'taken' } });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
