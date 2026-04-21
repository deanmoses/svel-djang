import { createDeleteSubmitter } from '$lib/delete-flow';
import type { components } from '$lib/api/schema';

export type DeleteResponse = components['schemas']['TaxonomyDeleteResponseSchema'];

export const submitDelete = createDeleteSubmitter<DeleteResponse>(
	'/api/corporate-entities/{slug}/delete/'
);
