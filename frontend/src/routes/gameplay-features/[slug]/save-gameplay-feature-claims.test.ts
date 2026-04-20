import { beforeEach, describe, expect, it, vi } from 'vitest';

import { saveGameplayFeatureClaims } from './save-gameplay-feature-claims';

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

describe('saveGameplayFeatureClaims', () => {
	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		invalidateAll.mockResolvedValue(undefined);
	});

	it('PATCHes the gameplay-features claims endpoint with field changes', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'pop-bumper' }, error: undefined });

		const result = await saveGameplayFeatureClaims('pop-bumper', {
			fields: { name: 'Pop Bumper' }
		});

		expect(PATCH).toHaveBeenCalledWith('/api/gameplay-features/{slug}/claims/', {
			params: { path: { slug: 'pop-bumper' } },
			body: { fields: { name: 'Pop Bumper' }, note: '' }
		});
		expect(invalidateAll).toHaveBeenCalledTimes(1);
		expect(result).toEqual({ ok: true, updatedSlug: 'pop-bumper' });
	});

	it('PATCHes parents and aliases when supplied', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'pop-bumper' }, error: undefined });

		await saveGameplayFeatureClaims('pop-bumper', {
			parents: ['physical-feature', 'defense'],
			aliases: ['Pop'],
			note: 'rationale'
		});

		expect(PATCH).toHaveBeenCalledWith('/api/gameplay-features/{slug}/claims/', {
			params: { path: { slug: 'pop-bumper' } },
			body: {
				fields: {},
				note: 'rationale',
				parents: ['physical-feature', 'defense'],
				aliases: ['Pop']
			}
		});
	});

	it('returns the renamed slug when the response includes a new one', async () => {
		PATCH.mockResolvedValueOnce({ data: { slug: 'bumper' }, error: undefined });

		const result = await saveGameplayFeatureClaims('pop-bumper', {
			fields: { slug: 'bumper' }
		});

		expect(result).toEqual({ ok: true, updatedSlug: 'bumper' });
	});

	it('falls back to the original slug when the response omits one', async () => {
		PATCH.mockResolvedValueOnce({ data: undefined, error: undefined });

		const result = await saveGameplayFeatureClaims('pop-bumper', { fields: {} });

		expect(result).toEqual({ ok: true, updatedSlug: 'pop-bumper' });
	});

	it('returns parsed field errors on 422 and skips invalidateAll', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: {
				detail: {
					message: 'invalid',
					field_errors: { parents: 'would create a cycle' },
					form_errors: []
				}
			}
		});

		const result = await saveGameplayFeatureClaims('pop-bumper', {
			parents: ['descendant-of-pop-bumper']
		});

		expect(result).toEqual({
			ok: false,
			error: 'parents: would create a cycle',
			fieldErrors: { parents: 'would create a cycle' }
		});
		expect(invalidateAll).not.toHaveBeenCalled();
	});

	it('returns a generic error message when the response has no detail.message', async () => {
		PATCH.mockResolvedValueOnce({
			data: undefined,
			error: { detail: 'server exploded' }
		});

		const result = await saveGameplayFeatureClaims('pop-bumper', { fields: {} });

		expect(result).toEqual({ ok: false, error: 'server exploded', fieldErrors: {} });
		expect(invalidateAll).not.toHaveBeenCalled();
	});
});
