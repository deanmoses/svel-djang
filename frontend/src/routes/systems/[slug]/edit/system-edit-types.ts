import type { components } from '$lib/api/schema';

export type SystemEditView = Pick<
	components['schemas']['SystemDetailSchema'],
	'name' | 'slug' | 'description' | 'manufacturer' | 'technology_subgeneration'
>;
