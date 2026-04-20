import type { EditSectionDef } from './edit-section-def';

export type SimpleTaxonomyEditSectionKey = 'name' | 'description' | 'display-order';

export type SimpleTaxonomyEditSectionDef = EditSectionDef<SimpleTaxonomyEditSectionKey>;

export const SIMPLE_TAXONOMY_EDIT_SECTIONS: SimpleTaxonomyEditSectionDef[] = [
	{
		key: 'name',
		segment: 'name',
		label: 'Name',
		showCitation: true,
		showMixedEditWarning: false
	},
	{
		key: 'description',
		segment: 'description',
		label: 'Description',
		showCitation: false,
		showMixedEditWarning: false
	},
	{
		key: 'display-order',
		segment: 'display-order',
		label: 'Display order',
		showCitation: false,
		showMixedEditWarning: false
	}
];

export function findSimpleTaxonomySectionBySegment(
	segment: string
): SimpleTaxonomyEditSectionDef | undefined {
	return SIMPLE_TAXONOMY_EDIT_SECTIONS.find((section) => section.segment === segment);
}

export function findSimpleTaxonomySectionByKey(
	key: SimpleTaxonomyEditSectionKey
): SimpleTaxonomyEditSectionDef | undefined {
	return SIMPLE_TAXONOMY_EDIT_SECTIONS.find((section) => section.key === key);
}

export function defaultSimpleTaxonomySectionSegment(): string {
	return 'name';
}
