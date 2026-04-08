import { describe, expect, it } from 'vitest';

import {
	buildModelPatchBody,
	modelToFormFields,
	type CreditRow,
	type GameplayFeatureRow,
	type ModelEditState,
	type ModelEditView,
	type ModelFormFields
} from './model-edit';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const baseModel: ModelEditView = {
	slug: 'medieval-madness',
	name: 'Medieval Madness',
	description: { text: 'Castle bashers.' },
	year: 1997,
	month: 6,
	player_count: 4,
	flipper_count: 2,
	production_quantity: '4016',
	ipdb_id: 4032,
	opdb_id: 'G5pe4',
	pinside_id: 1800,
	ipdb_rating: 8.5,
	pinside_rating: 9.1,
	corporate_entity: { slug: 'williams-1985' },
	technology_generation: { slug: 'solid-state' },
	technology_subgeneration: null,
	display_type: { slug: 'dmd' },
	display_subtype: null,
	cabinet: { slug: 'standard' },
	game_format: { slug: 'standard' },
	system: { slug: 'wpc-95' },
	variant_of: { slug: 'medieval-madness-le' },
	converted_from: null,
	remake_of: null,
	themes: [{ slug: 'medieval' }, { slug: 'fantasy' }],
	tags: [{ slug: 'classic' }],
	reward_types: [{ slug: 'multiball' }],
	gameplay_features: [
		{ slug: 'ramps', count: 3 },
		{ slug: 'pop-bumpers', count: 2 }
	],
	credits: [
		{
			person: { name: 'Pat Lawlor', slug: 'pat-lawlor' },
			role: 'design',
			role_display: 'Design',
			role_sort_order: 1
		},
		{
			person: { name: 'Greg Freres', slug: 'greg-freres' },
			role: 'art',
			role_display: 'Art',
			role_sort_order: 2
		}
	],
	abbreviations: ['MM']
};

function stateFromModel(model: ModelEditView, overrides?: Partial<ModelEditState>): ModelEditState {
	return {
		fields: modelToFormFields(model),
		themes: model.themes.map((t) => t.slug),
		tags: (model.tags ?? []).map((t) => t.slug),
		rewardTypes: model.reward_types.map((rt) => rt.slug),
		gameplayFeatures: model.gameplay_features.map((gf) => ({
			slug: gf.slug,
			count: gf.count ?? null
		})),
		credits: model.credits.map((c) => ({
			person_slug: c.person.slug,
			role: c.role
		})),
		abbreviations: [...model.abbreviations],
		...overrides
	};
}

// ---------------------------------------------------------------------------
// modelToFormFields
// ---------------------------------------------------------------------------

describe('modelToFormFields', () => {
	it('converts model data to form state', () => {
		const fields = modelToFormFields(baseModel);
		expect(fields.slug).toBe('medieval-madness');
		expect(fields.name).toBe('Medieval Madness');
		expect(fields.description).toBe('Castle bashers.');
		expect(fields.year).toBe(1997);
		expect(fields.corporate_entity).toBe('williams-1985');
		expect(fields.system).toBe('wpc-95');
	});

	it('extracts hierarchy FK slugs', () => {
		const fields = modelToFormFields(baseModel);
		expect(fields.variant_of).toBe('medieval-madness-le');
		expect(fields.converted_from).toBe('');
		expect(fields.remake_of).toBe('');
	});

	it('converts null FKs to empty strings', () => {
		const fields = modelToFormFields({ ...baseModel, technology_subgeneration: null });
		expect(fields.technology_subgeneration).toBe('');
	});

	it('converts null scalars to empty strings', () => {
		const fields = modelToFormFields({ ...baseModel, year: null, month: null });
		expect(fields.year).toBe('');
		expect(fields.month).toBe('');
	});

	it('handles missing description', () => {
		const fields = modelToFormFields({ ...baseModel, description: null });
		expect(fields.description).toBe('');
	});
});

// ---------------------------------------------------------------------------
// buildModelPatchBody — no-op
// ---------------------------------------------------------------------------

describe('buildModelPatchBody — no-op', () => {
	it('returns null when nothing changed', () => {
		const state = stateFromModel(baseModel);
		expect(buildModelPatchBody(state, baseModel)).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// buildModelPatchBody — scalar fields
// ---------------------------------------------------------------------------

describe('buildModelPatchBody — scalars', () => {
	it('detects changed scalar fields', () => {
		const fields: ModelFormFields = {
			...modelToFormFields(baseModel),
			slug: 'medieval-madness-remastered',
			name: 'Medieval Madness Remake',
			year: 2024
		};
		const state = stateFromModel(baseModel, { fields });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body).not.toBeNull();
		expect(body.fields).toEqual({
			slug: 'medieval-madness-remastered',
			name: 'Medieval Madness Remake',
			year: 2024
		});
	});

	it('sends null for cleared fields', () => {
		const fields: ModelFormFields = {
			...modelToFormFields(baseModel),
			year: '',
			month: ''
		};
		const state = stateFromModel(baseModel, { fields });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.fields.year).toBeNull();
		expect(body.fields.month).toBeNull();
	});

	it('sends null for cleared FK fields', () => {
		const fields: ModelFormFields = {
			...modelToFormFields(baseModel),
			corporate_entity: ''
		};
		const state = stateFromModel(baseModel, { fields });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.fields.corporate_entity).toBeNull();
	});

	it('detects changed hierarchy FK', () => {
		const fields: ModelFormFields = {
			...modelToFormFields(baseModel),
			variant_of: 'some-other-model'
		};
		const state = stateFromModel(baseModel, { fields });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.fields.variant_of).toBe('some-other-model');
	});

	it('sends null for cleared hierarchy FK', () => {
		const fields: ModelFormFields = {
			...modelToFormFields(baseModel),
			variant_of: ''
		};
		const state = stateFromModel(baseModel, { fields });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.fields.variant_of).toBeNull();
	});

	it('omits relationship fields when only scalars changed', () => {
		const fields: ModelFormFields = { ...modelToFormFields(baseModel), name: 'New Name' };
		const state = stateFromModel(baseModel, { fields });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.themes).toBeNull();
		expect(body.tags).toBeNull();
		expect(body.reward_types).toBeNull();
		expect(body.gameplay_features).toBeNull();
		expect(body.credits).toBeNull();
		expect(body.abbreviations).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// buildModelPatchBody — M2M relationships
// ---------------------------------------------------------------------------

describe('buildModelPatchBody — M2M', () => {
	it('detects added themes', () => {
		const state = stateFromModel(baseModel, {
			themes: ['medieval', 'fantasy', 'horror']
		});
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.themes).toEqual(['medieval', 'fantasy', 'horror']);
		expect(body.tags).toBeNull();
	});

	it('detects removed themes', () => {
		const state = stateFromModel(baseModel, { themes: ['medieval'] });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.themes).toEqual(['medieval']);
	});

	it('detects tag changes', () => {
		const state = stateFromModel(baseModel, { tags: ['classic', 'widebody'] });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.tags).toEqual(['classic', 'widebody']);
	});

	it('detects cleared reward types', () => {
		const state = stateFromModel(baseModel, { rewardTypes: [] });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.reward_types).toEqual([]);
	});

	it('ignores reordering (compares sorted)', () => {
		const state = stateFromModel(baseModel, { themes: ['fantasy', 'medieval'] });
		expect(buildModelPatchBody(state, baseModel)).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// buildModelPatchBody — gameplay features
// ---------------------------------------------------------------------------

describe('buildModelPatchBody — gameplay features', () => {
	it('detects added feature', () => {
		const gf: GameplayFeatureRow[] = [
			{ slug: 'ramps', count: 3 },
			{ slug: 'pop-bumpers', count: 2 },
			{ slug: 'loops', count: 1 }
		];
		const state = stateFromModel(baseModel, { gameplayFeatures: gf });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.gameplay_features).toHaveLength(3);
		expect(body.gameplay_features!.find((f) => f.slug === 'loops')).toEqual({
			slug: 'loops',
			count: 1
		});
	});

	it('detects count-only change', () => {
		const gf: GameplayFeatureRow[] = [
			{ slug: 'ramps', count: 5 },
			{ slug: 'pop-bumpers', count: 2 }
		];
		const state = stateFromModel(baseModel, { gameplayFeatures: gf });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.gameplay_features).not.toBeNull();
		expect(body.gameplay_features!.find((f) => f.slug === 'ramps')!.count).toBe(5);
	});

	it('detects removed feature', () => {
		const gf: GameplayFeatureRow[] = [{ slug: 'ramps', count: 3 }];
		const state = stateFromModel(baseModel, { gameplayFeatures: gf });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.gameplay_features).toEqual([{ slug: 'ramps', count: 3 }]);
	});

	it('filters out blank rows', () => {
		const gf: GameplayFeatureRow[] = [
			{ slug: 'ramps', count: 3 },
			{ slug: '', count: null },
			{ slug: 'pop-bumpers', count: 2 },
			{ slug: 'loops', count: null }
		];
		const state = stateFromModel(baseModel, { gameplayFeatures: gf });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.gameplay_features!.every((f) => f.slug !== '')).toBe(true);
		expect(body.gameplay_features).toHaveLength(3);
	});

	it('blank rows do not trigger a false change', () => {
		const gf: GameplayFeatureRow[] = [
			{ slug: 'ramps', count: 3 },
			{ slug: '', count: null },
			{ slug: 'pop-bumpers', count: 2 }
		];
		const state = stateFromModel(baseModel, { gameplayFeatures: gf });
		expect(buildModelPatchBody(state, baseModel)).toBeNull();
	});

	it('no change when features match (ignoring order)', () => {
		const gf: GameplayFeatureRow[] = [
			{ slug: 'pop-bumpers', count: 2 },
			{ slug: 'ramps', count: 3 }
		];
		const state = stateFromModel(baseModel, { gameplayFeatures: gf });
		expect(buildModelPatchBody(state, baseModel)).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// buildModelPatchBody — credits
// ---------------------------------------------------------------------------

describe('buildModelPatchBody — credits', () => {
	it('detects added credit', () => {
		const credits: CreditRow[] = [
			{ person_slug: 'pat-lawlor', role: 'design' },
			{ person_slug: 'greg-freres', role: 'art' },
			{ person_slug: 'john-youssi', role: 'software' }
		];
		const state = stateFromModel(baseModel, { credits });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.credits).toHaveLength(3);
		expect(body.credits!.find((c) => c.person_slug === 'john-youssi')).toEqual({
			person_slug: 'john-youssi',
			role: 'software'
		});
	});

	it('detects removed credit', () => {
		const credits: CreditRow[] = [{ person_slug: 'pat-lawlor', role: 'design' }];
		const state = stateFromModel(baseModel, { credits });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.credits).toEqual([{ person_slug: 'pat-lawlor', role: 'design' }]);
	});

	it('filters out incomplete rows', () => {
		const credits: CreditRow[] = [
			{ person_slug: 'pat-lawlor', role: 'design' },
			{ person_slug: '', role: 'art' },
			{ person_slug: 'greg-freres', role: '' },
			{ person_slug: 'john-youssi', role: 'software' }
		];
		const state = stateFromModel(baseModel, { credits });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.credits!.every((c) => c.person_slug !== '' && c.role !== '')).toBe(true);
		expect(body.credits).toHaveLength(2);
	});

	it('blank rows do not trigger a false change', () => {
		const credits: CreditRow[] = [
			{ person_slug: 'pat-lawlor', role: 'design' },
			{ person_slug: '', role: '' },
			{ person_slug: 'greg-freres', role: 'art' }
		];
		const state = stateFromModel(baseModel, { credits });
		expect(buildModelPatchBody(state, baseModel)).toBeNull();
	});

	it('no change when credits match (ignoring order)', () => {
		const credits: CreditRow[] = [
			{ person_slug: 'greg-freres', role: 'art' },
			{ person_slug: 'pat-lawlor', role: 'design' }
		];
		const state = stateFromModel(baseModel, { credits });
		expect(buildModelPatchBody(state, baseModel)).toBeNull();
	});

	it('same person different roles counts as change', () => {
		const credits: CreditRow[] = [
			{ person_slug: 'pat-lawlor', role: 'design' },
			{ person_slug: 'pat-lawlor', role: 'software' }
		];
		const state = stateFromModel(baseModel, { credits });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.credits).toHaveLength(2);
	});
});

// ---------------------------------------------------------------------------
// buildModelPatchBody — abbreviations
// ---------------------------------------------------------------------------

describe('buildModelPatchBody — abbreviations', () => {
	it('detects added abbreviations', () => {
		const state = stateFromModel(baseModel, { abbreviations: ['MM', 'MMR'] });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.abbreviations).toEqual(['MM', 'MMR']);
	});

	it('detects cleared abbreviations', () => {
		const state = stateFromModel(baseModel, { abbreviations: [] });
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.abbreviations).toEqual([]);
	});

	it('no change when abbreviations match', () => {
		const state = stateFromModel(baseModel, { abbreviations: ['MM'] });
		expect(buildModelPatchBody(state, baseModel)).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// buildModelPatchBody — mixed changes
// ---------------------------------------------------------------------------

describe('buildModelPatchBody — mixed', () => {
	it('builds correct body with scalar + relationship + feature changes', () => {
		const fields: ModelFormFields = { ...modelToFormFields(baseModel), year: 1998 };
		const state = stateFromModel(baseModel, {
			fields,
			themes: ['medieval'],
			gameplayFeatures: [{ slug: 'ramps', count: 5 }],
			abbreviations: ['MM', 'MMR']
		});
		const body = buildModelPatchBody(state, baseModel)!;
		expect(body.fields).toEqual({ year: 1998 });
		expect(body.themes).toEqual(['medieval']);
		expect(body.tags).toBeNull();
		expect(body.reward_types).toBeNull();
		expect(body.gameplay_features).toEqual([{ slug: 'ramps', count: 5 }]);
		expect(body.credits).toBeNull();
		expect(body.abbreviations).toEqual(['MM', 'MMR']);
	});
});
