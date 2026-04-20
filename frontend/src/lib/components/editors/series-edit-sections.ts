import type { EditSectionDef } from './edit-section-def';

export type SeriesEditSectionKey = 'name' | 'description';

export type SeriesEditSectionDef = EditSectionDef<SeriesEditSectionKey> & {
	usesSectionEditorForm: boolean;
};

export const SERIES_EDIT_SECTIONS: SeriesEditSectionDef[] = [
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

export function findSeriesSectionBySegment(segment: string): SeriesEditSectionDef | undefined {
	return SERIES_EDIT_SECTIONS.find((section) => section.segment === segment);
}

export function findSeriesSectionByKey(
	key: SeriesEditSectionKey
): SeriesEditSectionDef | undefined {
	return SERIES_EDIT_SECTIONS.find((section) => section.key === key);
}

export function defaultSeriesSectionSegment(): string {
	return 'name';
}
