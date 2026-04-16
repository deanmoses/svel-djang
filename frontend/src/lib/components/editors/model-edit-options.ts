/**
 * Shared helper for fetching model edit options.
 *
 * Used by section editors that need dropdown options (people, roles,
 * taxonomy terms, etc.). Eliminates duplicated fetch + type boilerplate.
 */

import client from '$lib/api/client';
import type { components } from '$lib/api/schema';

export type ModelEditOptions = components['schemas']['ModelEditOptionsSchema'];

export const EMPTY_EDIT_OPTIONS: ModelEditOptions = {
	themes: [],
	tags: [],
	reward_types: [],
	gameplay_features: [],
	technology_generations: [],
	technology_subgenerations: [],
	display_types: [],
	display_subtypes: [],
	cabinets: [],
	game_formats: [],
	systems: [],
	corporate_entities: [],
	people: [],
	credit_roles: [],
	titles: [],
	models: []
};

let cached: Promise<ModelEditOptions> | null = null;

/** Fetch model edit options (cached for the session). */
export function fetchModelEditOptions(): Promise<ModelEditOptions> {
	if (!cached) {
		cached = client
			.GET('/api/models/edit-options/')
			.then(({ data }) => data ?? EMPTY_EDIT_OPTIONS)
			.catch(() => {
				cached = null;
				return EMPTY_EDIT_OPTIONS;
			});
	}
	return cached;
}
