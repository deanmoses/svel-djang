import { stringSetChanged } from '$lib/edit-helpers';

export type TitleEditView = {
	slug: string;
	name: string;
	description?: { text: string } | null;
	franchise?: { slug: string; name: string } | null;
	abbreviations: string[];
	machines: Array<{
		slug: string;
		name: string;
		variants?: Array<{ slug: string; name: string }>;
	}>;
	model_detail?: { slug: string } | null;
};

export type TitleEditFormState = {
	slug: string;
	name: string;
	description: string;
	franchiseSlug: string;
	abbreviationsText: string;
};

type TitlePatchBody = {
	fields: Record<string, unknown>;
	abbreviations: string[] | null;
};

function normalizeAbbreviations(values: string[]): string[] {
	const seen = new Set<string>();
	const normalized: string[] = [];

	for (const rawValue of values) {
		const value = rawValue.trim();
		if (!value || seen.has(value)) continue;
		seen.add(value);
		normalized.push(value);
	}

	return normalized;
}

export function parseAbbreviations(text: string): string[] {
	return normalizeAbbreviations(text.split(/[\n,]/));
}

export function titleToFormState(title: TitleEditView): TitleEditFormState {
	return {
		slug: title.slug,
		name: title.name,
		description: title.description?.text ?? '',
		franchiseSlug: title.franchise?.slug ?? '',
		abbreviationsText: title.abbreviations.join(', ')
	};
}

function buildChangedTitleFields(
	form: TitleEditFormState,
	title: TitleEditView
): Record<string, unknown> {
	const original = titleToFormState(title);
	const changed: Record<string, unknown> = {};

	if (form.name !== original.name) changed.name = form.name === '' ? null : form.name;
	if (form.slug !== original.slug) changed.slug = form.slug === '' ? null : form.slug;
	if (form.description !== original.description) {
		changed.description = form.description === '' ? null : form.description;
	}
	if (form.franchiseSlug !== original.franchiseSlug) {
		changed.franchise = form.franchiseSlug === '' ? null : form.franchiseSlug;
	}

	return changed;
}

function abbreviationsChanged(form: TitleEditFormState, title: TitleEditView): boolean {
	return stringSetChanged(
		parseAbbreviations(form.abbreviationsText),
		normalizeAbbreviations(title.abbreviations)
	);
}

export function buildTitlePatchBody(
	form: TitleEditFormState,
	title: TitleEditView
): TitlePatchBody | null {
	const fields = buildChangedTitleFields(form, title);
	const hasFields = Object.keys(fields).length > 0;
	const hasAbbreviations = abbreviationsChanged(form, title);

	if (!hasFields && !hasAbbreviations) return null;

	return {
		fields,
		abbreviations: hasAbbreviations ? parseAbbreviations(form.abbreviationsText) : null
	};
}

export function buildModelBoundary(title: TitleEditView): {
	modelLinks: Array<{ slug: string; name: string }>;
	singleModelActions: { editHref: string; sourcesHref: string } | null;
} {
	const singleModelSlug = title.model_detail?.slug ?? null;
	const modelLinks = singleModelSlug
		? []
		: title.machines.flatMap((machine) => [
				{
					slug: machine.slug,
					name: machine.name
				},
				...(machine.variants ?? []).map((variant) => ({
					slug: variant.slug,
					name: variant.name
				}))
			]);

	return {
		modelLinks,
		singleModelActions: singleModelSlug
			? {
					editHref: `/models/${singleModelSlug}/edit`,
					sourcesHref: `/models/${singleModelSlug}/sources`
				}
			: null
	};
}
