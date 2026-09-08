import type { UploadedMediaSchema } from '$lib/api/schema';

type UploadedMedia = UploadedMediaSchema;

export function makeMedia(index: number, overrides: Partial<UploadedMedia> = {}): UploadedMedia {
  return {
    asset_uuid: `asset-${index}`,
    category: 'cabinet',
    is_primary: index === 1,
    uploaded_by_username: 'moses',
    renditions: {
      thumb: `https://example.com/thumb-${index}.jpg`,
      display: `https://example.com/display-${index}.jpg`,
    },
    ...overrides,
  };
}

export const MEDIA_ITEMS = [
  makeMedia(1, { category: 'cabinet', is_primary: true }),
  makeMedia(2, { category: 'backglass', uploaded_by_username: 'jane' }),
  makeMedia(3, { category: 'cabinet' }),
];
