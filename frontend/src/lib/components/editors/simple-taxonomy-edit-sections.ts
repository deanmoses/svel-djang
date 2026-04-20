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

export function defaultSimpleTaxonomySectionSegment(): string {
	return 'name';
}
