import type { EditSectionDef } from './edit-section-def';

export type FranchiseEditSectionKey = 'name' | 'description';

export type FranchiseEditSectionDef = EditSectionDef<FranchiseEditSectionKey> & {
	usesSectionEditorForm: boolean;
};

export const FRANCHISE_EDIT_SECTIONS: FranchiseEditSectionDef[] = [
	{
		key: 'name',
		segment: 'name',
		label: 'Name',
		showCitation: true,
		showMixedEditWarning: false,
		usesSectionEditorForm: true
	},
	{
		key: 'description',
		segment: 'description',
		label: 'Description',
		showCitation: false,
		showMixedEditWarning: false,
		usesSectionEditorForm: true
	}
];

export function findFranchiseSectionBySegment(
	segment: string
): FranchiseEditSectionDef | undefined {
	return FRANCHISE_EDIT_SECTIONS.find((section) => section.segment === segment);
}

export function findFranchiseSectionByKey(
	key: FranchiseEditSectionKey
): FranchiseEditSectionDef | undefined {
	return FRANCHISE_EDIT_SECTIONS.find((section) => section.key === key);
}

export function defaultFranchiseSectionSegment(): string {
	return 'name';
}
