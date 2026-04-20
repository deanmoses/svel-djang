import { describe, expect, it } from 'vitest';

import { modelHasTitleOwnedIdentity } from './catalog-rules';

describe('modelHasTitleOwnedIdentity', () => {
	it('is true for a base model that is the only model on its title with no variants', () => {
		expect(
			modelHasTitleOwnedIdentity({
				title_models: [{ variants: [] }],
				variant_of: null
			})
		).toBe(true);
	});

	it('is false when the base model has any variants (no combined title editor to use)', () => {
		expect(
			modelHasTitleOwnedIdentity({
				title_models: [{ variants: [{}, {}] }],
				variant_of: null
			})
		).toBe(false);
	});

	it('is false when the title has multiple base models', () => {
		expect(
			modelHasTitleOwnedIdentity({
				title_models: [{ variants: [] }, { variants: [] }],
				variant_of: null
			})
		).toBe(false);
	});

	it('is false for variants (variant identity lives on the variant, not a title)', () => {
		expect(
			modelHasTitleOwnedIdentity({
				title_models: [{ variants: [] }],
				variant_of: { slug: 'parent' }
			})
		).toBe(false);
	});

	it('is false for a model whose title has no base models (defensive)', () => {
		expect(
			modelHasTitleOwnedIdentity({
				title_models: [],
				variant_of: null
			})
		).toBe(false);
	});
});
