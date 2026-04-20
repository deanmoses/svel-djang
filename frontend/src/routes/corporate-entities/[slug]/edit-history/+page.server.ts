import type { PageServerLoad } from './$types';
import { loadEditHistory } from '$lib/edit-history-loader';

export const load: PageServerLoad = (event) =>
	loadEditHistory(event, 'corporate-entity', event.params.slug);
