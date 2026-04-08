import type { components } from '$lib/api/schema';

type UploadedMedia = components['schemas']['UploadedMediaSchema'];

export function makeMedia(index: number, overrides: Partial<UploadedMedia> = {}): UploadedMedia {
	return {
		asset_uuid: `asset-${index}`,
		category: 'Cabinet',
		is_primary: index === 1,
		uploaded_by_username: 'moses',
		renditions: {
			thumb: `https://example.com/thumb-${index}.jpg`,
			display: `https://example.com/display-${index}.jpg`
		},
		...overrides
	} as UploadedMedia;
}

export const MEDIA_ITEMS = [
	makeMedia(1, { category: 'Cabinet', is_primary: true }),
	makeMedia(2, { category: 'Backglass', uploaded_by_username: 'jane' }),
	makeMedia(3, { category: 'Cabinet', uploaded_by_username: null as never })
];
