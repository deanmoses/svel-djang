/**
 * Shared pure helpers for hierarchical entity editing (Theme, GameplayFeature).
 *
 * These entities share the same edit shape: scalar fields (name, description),
 * parent slugs and aliases — mapped to HierarchyClaimPatchSchema.
 */

import { diffScalarFields, slugSetChanged, stringSetChanged } from '$lib/edit-helpers';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type HierarchyEditView = {
	name: string;
	description?: { text: string } | null;
	parents?: { slug: string }[];
	aliases?: string[];
};

export type HierarchyFormFields = {
	name: string;
	description: string;
};

export type HierarchyEditState = {
	fields: HierarchyFormFields;
	parents: string[];
	aliases: string[];
};

export type HierarchyPatchBody = {
	fields: Record<string, unknown>;
	parents: string[] | null;
	aliases: string[] | null;
};

// ---------------------------------------------------------------------------
// Entity → form state
// ---------------------------------------------------------------------------

export function hierarchyToFormFields(entity: HierarchyEditView): HierarchyFormFields {
	return {
		name: entity.name,
		description: entity.description?.text ?? ''
	};
}

// ---------------------------------------------------------------------------
// Build PATCH body
// ---------------------------------------------------------------------------

export function buildHierarchyPatchBody(
	state: HierarchyEditState,
	entity: HierarchyEditView
): HierarchyPatchBody | null {
	const original = hierarchyToFormFields(entity);
	const fields = diffScalarFields(state.fields, original);
	const hasFields = Object.keys(fields).length > 0;
	const hasParents = slugSetChanged(state.parents, entity.parents ?? []);
	const hasAliases = stringSetChanged(state.aliases, entity.aliases ?? []);

	if (!hasFields && !hasParents && !hasAliases) {
		return null;
	}

	return {
		fields: hasFields ? fields : {},
		parents: hasParents ? state.parents : null,
		aliases: hasAliases ? state.aliases : null
	};
}
