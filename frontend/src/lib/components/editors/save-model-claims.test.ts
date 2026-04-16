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

import { saveModelClaims } from './save-model-claims';

describe('saveModelClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
	});

	it('returns ok and invalidates on success', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		const result = await saveModelClaims('medieval-madness', {
			fields: { description: 'new text' }
		});

		expect(result).toEqual({ ok: true });
		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { description: 'new text' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledOnce();
	});

	it('extracts detail string from error object', async () => {
		PATCH.mockResolvedValue({
			data: undefined,
			error: { detail: 'Ensure this value is less than or equal to 10.' }
		});

		const result = await saveModelClaims('medieval-madness', {
			fields: { pinside_rating: 10234 }
		});

		expect(result).toEqual({ ok: false, error: 'Ensure this value is less than or equal to 10.' });
		expect(invalidateAll).not.toHaveBeenCalled();
	});

	it('joins array-of-objects detail into a readable message', async () => {
		PATCH.mockResolvedValue({
			data: undefined,
			error: {
				detail: [
					{
						loc: ['body', 'fields', 'year'],
						msg: 'value is not a valid integer',
						type: 'type_error'
					}
				]
			}
		});

		const result = await saveModelClaims('medieval-madness', {
			fields: { year: 'not-a-number' }
		});

		expect(result).toEqual({ ok: false, error: 'year: value is not a valid integer' });
	});

	it('handles string errors', async () => {
		PATCH.mockResolvedValue({ data: undefined, error: 'Something went wrong' });

		const result = await saveModelClaims('medieval-madness', {
			fields: { description: 'x' }
		});

		expect(result).toEqual({ ok: false, error: 'Something went wrong' });
	});

	it('falls back to JSON for unknown error shapes', async () => {
		PATCH.mockResolvedValue({ data: undefined, error: { unexpected: 'shape' } });

		const result = await saveModelClaims('medieval-madness', {
			fields: { description: 'x' }
		});

		expect(result).toEqual({ ok: false, error: '{"unexpected":"shape"}' });
	});

	it('sends credits-only body with default fields', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		const credits = [{ person_slug: 'pat-lawlor', role: 'game-design' }];
		await saveModelClaims('medieval-madness', { credits });

		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: {}, note: '', credits }
		});
	});

	it('passes note override', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		await saveModelClaims('medieval-madness', {
			fields: { year: 1997 },
			note: 'Corrected per IPDB'
		});

		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { year: 1997 }, note: 'Corrected per IPDB' }
		});
	});

	it('passes citation override', async () => {
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);

		const citation = { citation_instance_id: 42 };
		await saveModelClaims('medieval-madness', {
			fields: { year: 1997 },
			citation
		});

		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { year: 1997 }, note: '', citation }
		});
	});
});
