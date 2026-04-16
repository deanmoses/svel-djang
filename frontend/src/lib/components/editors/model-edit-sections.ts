export type ModelEditSectionKey =
	| 'basics'
	| 'overview'
	| 'specifications'
	| 'features'
	| 'people'
	| 'relationships'
	| 'external-data'
	| 'media';

export type ModelEditSectionDef = {
	key: ModelEditSectionKey;
	/** URL segment for the mobile edit route, e.g. 'external-data' */
	segment: string;
	label: string;
	showCitation: boolean;
	showMixedEditWarning: boolean;
	/** false for media — uses immediate-action Modal, not SectionEditorForm */
	usesSectionEditorForm: boolean;
};

export const MODEL_EDIT_SECTIONS: ModelEditSectionDef[] = [
	{
		key: 'basics',
		segment: 'basics',
		label: 'Basics',
		showCitation: true,
		showMixedEditWarning: true,
		usesSectionEditorForm: true
	},
	{
		key: 'overview',
		segment: 'overview',
		label: 'Overview',
		showCitation: false,
		showMixedEditWarning: false,
		usesSectionEditorForm: true
	},
	{
		key: 'specifications',
		segment: 'specifications',
		label: 'Specifications',
		showCitation: true,
		showMixedEditWarning: true,
		usesSectionEditorForm: true
	},
	{
		key: 'features',
		segment: 'features',
		label: 'Features',
		showCitation: true,
		showMixedEditWarning: true,
		usesSectionEditorForm: true
	},
	{
		key: 'people',
		segment: 'people',
		label: 'People',
		showCitation: true,
		showMixedEditWarning: true,
		usesSectionEditorForm: true
	},
	{
		key: 'relationships',
		segment: 'relationships',
		label: 'Relationships',
		showCitation: true,
		showMixedEditWarning: true,
		usesSectionEditorForm: true
	},
	{
		key: 'external-data',
		segment: 'external-data',
		label: 'External Data',
		showCitation: true,
		showMixedEditWarning: true,
		usesSectionEditorForm: true
	},
	{
		key: 'media',
		segment: 'media',
		label: 'Media',
		showCitation: false,
		showMixedEditWarning: false,
		usesSectionEditorForm: false
	}
];

export function findSectionByKey(key: string): ModelEditSectionDef | undefined {
	return MODEL_EDIT_SECTIONS.find((s) => s.key === key);
}

export function findSectionBySegment(segment: string): ModelEditSectionDef | undefined {
	return MODEL_EDIT_SECTIONS.find((s) => s.segment === segment);
}
