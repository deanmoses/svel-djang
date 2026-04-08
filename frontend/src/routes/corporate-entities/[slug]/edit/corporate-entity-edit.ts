import { diffScalarFields, stringSetChanged } from '$lib/edit-helpers';

export type CorporateEntityEditView = {
	slug: string;
	name: string;
	description?: { text: string } | null;
	year_start?: number | null;
	year_end?: number | null;
	aliases?: string[];
};

export type CorporateEntityFormFields = {
	slug: string;
	name: string;
	description: string;
	year_start: string | number;
	year_end: string | number;
};

export type CorporateEntityEditState = {
	fields: CorporateEntityFormFields;
	aliases: string[];
};

type CorporateEntityPatchBody = {
	fields: Record<string, unknown>;
	aliases: string[] | null;
};

export function corporateEntityToFormFields(
	entity: CorporateEntityEditView
): CorporateEntityFormFields {
	return {
		slug: entity.slug,
		name: entity.name,
		description: entity.description?.text ?? '',
		year_start: entity.year_start ?? '',
		year_end: entity.year_end ?? ''
	};
}

export function buildCorporateEntityPatchBody(
	state: CorporateEntityEditState,
	entity: CorporateEntityEditView
): CorporateEntityPatchBody | null {
	const fields = diffScalarFields(state.fields, corporateEntityToFormFields(entity));
	const hasFields = Object.keys(fields).length > 0;
	const hasAliases = stringSetChanged(state.aliases, entity.aliases ?? []);

	if (!hasFields && !hasAliases) return null;

	return {
		fields,
		aliases: hasAliases ? state.aliases : null
	};
}
