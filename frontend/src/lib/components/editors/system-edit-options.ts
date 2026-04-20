/**
 * Cached fetchers for system edit dropdowns (manufacturer, technology subgeneration).
 *
 * Parallel to title-edit-options.ts. Each list is cached per-session.
 */

import client from '$lib/api/client';

export type SystemEditOption = {
	slug: string;
	label: string;
	count: number;
};

let cachedManufacturers: Promise<SystemEditOption[]> | null = null;
let cachedTechSubgens: Promise<SystemEditOption[]> | null = null;

export function fetchManufacturerOptions(): Promise<SystemEditOption[]> {
	if (!cachedManufacturers) {
		cachedManufacturers = client
			.GET('/api/manufacturers/all/')
			.then(({ data }) =>
				(data ?? []).map((m) => ({ slug: m.slug, label: m.name, count: m.model_count }))
			)
			.catch(() => {
				cachedManufacturers = null;
				return [];
			});
	}
	return cachedManufacturers;
}

export function fetchTechnologySubgenerationOptions(): Promise<SystemEditOption[]> {
	if (!cachedTechSubgens) {
		cachedTechSubgens = client
			.GET('/api/technology-subgenerations/')
			.then(({ data }) => (data ?? []).map((t) => ({ slug: t.slug, label: t.name, count: 0 })))
			.catch(() => {
				cachedTechSubgens = null;
				return [];
			});
	}
	return cachedTechSubgens;
}
