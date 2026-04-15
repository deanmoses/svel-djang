import { describe, expect, it, vi, beforeEach } from 'vitest';

const { PATCH } = vi.hoisted(() => ({
	PATCH: vi.fn()
}));

const { invalidateAll } = vi.hoisted(() => ({
	invalidateAll: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: { PATCH }
}));

vi.mock('$app/navigation', () => ({
	invalidateAll
}));

import { saveModelFields } from './save-model-fields';

describe('saveModelFields', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
	});

	it('returns ok and invalidates on success', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		const result = await saveModelFields('medieval-madness', { description: 'new text' });

		expect(result).toEqual({ ok: true });
		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { description: 'new text' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledOnce();
	});

	it('returns error string on failure', async () => {
		PATCH.mockResolvedValue({ data: undefined, error: { detail: 'bad request' } });

		const result = await saveModelFields('medieval-madness', { description: 'x' });

		expect(result).toEqual({ ok: false, error: '{"detail":"bad request"}' });
		expect(invalidateAll).not.toHaveBeenCalled();
	});

	it('handles string errors', async () => {
		PATCH.mockResolvedValue({ data: undefined, error: 'Something went wrong' });

		const result = await saveModelFields('medieval-madness', { description: 'x' });

		expect(result).toEqual({ ok: false, error: 'Something went wrong' });
	});
});
