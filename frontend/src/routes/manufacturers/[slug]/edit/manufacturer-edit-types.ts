import type { components } from '$lib/api/schema';

export type ManufacturerEditView = Pick<
	components['schemas']['ManufacturerDetailSchema'],
	'name' | 'slug' | 'website' | 'logo_url' | 'description'
>;
