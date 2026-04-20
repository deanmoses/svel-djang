import type { components } from '$lib/api/schema';

export type PersonEditView = Pick<
	components['schemas']['PersonDetailSchema'],
	| 'name'
	| 'slug'
	| 'description'
	| 'nationality'
	| 'birth_year'
	| 'birth_month'
	| 'birth_day'
	| 'birth_place'
	| 'death_year'
	| 'death_month'
	| 'death_day'
	| 'photo_url'
>;
