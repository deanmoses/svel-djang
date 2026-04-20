import type { components } from '$lib/api/schema';

export type SeriesEditView = Pick<
	components['schemas']['SeriesDetailSchema'],
	'name' | 'slug' | 'description'
>;
