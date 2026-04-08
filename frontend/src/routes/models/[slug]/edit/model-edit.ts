/**
 * Pure helper functions for MachineModel edit state.
 *
 * No Svelte imports, no component state — just plain-object transforms
 * that the Svelte page calls with current values.
 */

import { diffScalarFields, slugSetChanged, stringSetChanged } from '$lib/edit-helpers';

// ---------------------------------------------------------------------------
// FK field config — drives both modelToFormFields and template loops
// ---------------------------------------------------------------------------

export const TAXONOMY_FK_FIELDS = [
	{ field: 'corporate_entity', optionsKey: 'corporate_entities', label: 'Corporate entity' },
	{
		field: 'technology_generation',
		optionsKey: 'technology_generations',
		label: 'Technology generation'
	},
	{
		field: 'technology_subgeneration',
		optionsKey: 'technology_subgenerations',
		label: 'Technology subgeneration'
	},
	{ field: 'display_type', optionsKey: 'display_types', label: 'Display type' },
	{ field: 'display_subtype', optionsKey: 'display_subtypes', label: 'Display subtype' },
	{ field: 'cabinet', optionsKey: 'cabinets', label: 'Cabinet' },
	{ field: 'game_format', optionsKey: 'game_formats', label: 'Game format' },
	{ field: 'system', optionsKey: 'systems', label: 'System' }
] as const;

export const HIERARCHY_FK_FIELDS = [
	{ field: 'variant_of', optionsKey: 'models', label: 'Variant of' },
	{ field: 'converted_from', optionsKey: 'models', label: 'Converted from' },
	{ field: 'remake_of', optionsKey: 'models', label: 'Remake of' }
] as const;

const ALL_FK_FIELDS = [...TAXONOMY_FK_FIELDS, ...HIERARCHY_FK_FIELDS];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ModelEditView = {
	slug: string;
	name: string;
	description?: { text: string } | null;
	year?: number | null;
	month?: number | null;
	player_count?: number | null;
	flipper_count?: number | null;
	production_quantity: string;
	ipdb_id?: number | null;
	opdb_id?: string | null;
	pinside_id?: number | null;
	ipdb_rating?: number | null;
	pinside_rating?: number | null;
	corporate_entity?: { slug: string } | null;
	technology_generation?: { slug: string } | null;
	technology_subgeneration?: { slug: string } | null;
	display_type?: { slug: string } | null;
	display_subtype?: { slug: string } | null;
	cabinet?: { slug: string } | null;
	game_format?: { slug: string } | null;
	system?: { slug: string } | null;
	variant_of?: { slug: string } | null;
	converted_from?: { slug: string } | null;
	remake_of?: { slug: string } | null;
	themes: { slug: string }[];
	tags?: { slug: string }[];
	reward_types: { slug: string }[];
	gameplay_features: { slug: string; count?: number | null }[];
	credits: {
		person: { slug: string; name: string };
		role: string;
		role_display: string;
		role_sort_order: number;
	}[];
	abbreviations: string[];
};

export type ModelFormFields = {
	slug: string;
	name: string;
	description: string;
	year: string | number;
	month: string | number;
	player_count: string | number;
	flipper_count: string | number;
	production_quantity: string | number;
	ipdb_id: string | number;
	opdb_id: string;
	pinside_id: string | number;
	ipdb_rating: string | number;
	pinside_rating: string | number;
	corporate_entity: string;
	technology_generation: string;
	technology_subgeneration: string;
	display_type: string;
	display_subtype: string;
	cabinet: string;
	game_format: string;
	system: string;
	variant_of: string;
	converted_from: string;
	remake_of: string;
};

export type GameplayFeatureRow = {
	slug: string;
	count: number | null;
};

export type CreditRow = {
	person_slug: string;
	role: string;
};

export type ModelEditState = {
	fields: ModelFormFields;
	themes: string[];
	tags: string[];
	rewardTypes: string[];
	gameplayFeatures: GameplayFeatureRow[];
	credits: CreditRow[];
	abbreviations: string[];
};

export type ModelPatchBody = {
	fields: Record<string, unknown>;
	themes: string[] | null;
	tags: string[] | null;
	reward_types: string[] | null;
	gameplay_features: { slug: string; count: number | null }[] | null;
	credits: { person_slug: string; role: string }[] | null;
	abbreviations: string[] | null;
};

// ---------------------------------------------------------------------------
// Model → form state
// ---------------------------------------------------------------------------

export function modelToFormFields(m: ModelEditView): ModelFormFields {
	const fields: Record<string, unknown> = {
		slug: m.slug,
		name: m.name,
		description: m.description?.text ?? '',
		year: m.year ?? '',
		month: m.month ?? '',
		player_count: m.player_count ?? '',
		flipper_count: m.flipper_count ?? '',
		production_quantity: m.production_quantity,
		ipdb_id: m.ipdb_id ?? '',
		opdb_id: m.opdb_id ?? '',
		pinside_id: m.pinside_id ?? '',
		ipdb_rating: m.ipdb_rating ?? '',
		pinside_rating: m.pinside_rating ?? ''
	};
	for (const fk of ALL_FK_FIELDS) {
		const ref = m[fk.field as keyof ModelEditView] as { slug: string } | null | undefined;
		fields[fk.field] = ref?.slug ?? '';
	}
	return fields as ModelFormFields;
}

// ---------------------------------------------------------------------------
// Change detection (private helpers)
// ---------------------------------------------------------------------------

function gameplayFeaturesChanged(
	current: GameplayFeatureRow[],
	original: { slug: string; count?: number | null }[]
): boolean {
	const orig = original.map((gf) => `${gf.slug}:${gf.count ?? null}`).sort();
	const curr = current
		.filter((gf) => gf.slug !== '')
		.map((gf) => `${gf.slug}:${gf.count}`)
		.sort();
	return JSON.stringify(orig) !== JSON.stringify(curr);
}

function creditsChanged(
	current: CreditRow[],
	original: { person: { slug: string }; role: string }[]
): boolean {
	const orig = original.map((c) => `${c.person.slug}:${c.role}`).sort();
	const curr = current
		.filter((c) => c.person_slug !== '' && c.role !== '')
		.map((c) => `${c.person_slug}:${c.role}`)
		.sort();
	return JSON.stringify(orig) !== JSON.stringify(curr);
}

// ---------------------------------------------------------------------------
// Build PATCH body
// ---------------------------------------------------------------------------

export function buildModelPatchBody(
	state: ModelEditState,
	model: ModelEditView
): ModelPatchBody | null {
	const original = modelToFormFields(model);
	const fields = diffScalarFields(state.fields, original);
	const hasFields = Object.keys(fields).length > 0;
	const hasThemes = slugSetChanged(state.themes, model.themes);
	const hasTags = slugSetChanged(state.tags, model.tags ?? []);
	const hasRewardTypes = slugSetChanged(state.rewardTypes, model.reward_types);
	const hasFeatures = gameplayFeaturesChanged(state.gameplayFeatures, model.gameplay_features);
	const hasCredits = creditsChanged(state.credits, model.credits);
	const hasAbbrevs = stringSetChanged(state.abbreviations, model.abbreviations);

	if (
		!hasFields &&
		!hasThemes &&
		!hasTags &&
		!hasRewardTypes &&
		!hasFeatures &&
		!hasCredits &&
		!hasAbbrevs
	) {
		return null;
	}

	return {
		fields: hasFields ? fields : {},
		themes: hasThemes ? state.themes : null,
		tags: hasTags ? state.tags : null,
		reward_types: hasRewardTypes ? state.rewardTypes : null,
		gameplay_features: hasFeatures
			? state.gameplayFeatures
					.filter((gf) => gf.slug !== '')
					.map(({ slug, count }) => ({ slug, count }))
			: null,
		credits: hasCredits
			? state.credits
					.filter((c) => c.person_slug !== '' && c.role !== '')
					.map(({ person_slug, role }) => ({ person_slug, role }))
			: null,
		abbreviations: hasAbbrevs ? state.abbreviations : null
	};
}
