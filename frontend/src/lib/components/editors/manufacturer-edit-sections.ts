import type { EditSectionDef } from './edit-section-def';

export type ManufacturerEditSectionKey = 'name' | 'description' | 'basics';

export type ManufacturerEditSectionDef = EditSectionDef<ManufacturerEditSectionKey>;

export const MANUFACTURER_EDIT_SECTIONS: ManufacturerEditSectionDef[] = [
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
		key: 'basics',
		segment: 'basics',
		label: 'Basics',
		showCitation: true,
		showMixedEditWarning: true
	}
];

export function findManufacturerSectionBySegment(
	segment: string
): ManufacturerEditSectionDef | undefined {
	return MANUFACTURER_EDIT_SECTIONS.find((section) => section.segment === segment);
}

export function findManufacturerSectionByKey(
	key: ManufacturerEditSectionKey
): ManufacturerEditSectionDef | undefined {
	return MANUFACTURER_EDIT_SECTIONS.find((section) => section.key === key);
}

export function defaultManufacturerSectionSegment(): string {
	return 'name';
}
