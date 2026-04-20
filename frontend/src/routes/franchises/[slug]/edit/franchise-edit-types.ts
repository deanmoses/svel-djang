import type { components } from '$lib/api/schema';

export type FranchiseEditView = Pick<
	components['schemas']['FranchiseDetailSchema'],
	'name' | 'slug' | 'description'
>;
