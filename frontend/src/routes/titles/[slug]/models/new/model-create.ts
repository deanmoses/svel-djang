/**
 * Model Create slug projection.
 *
 * Model slugs are globally unique (``/models/{slug}`` routing), so a raw
 * slugify of the model name is almost never what the user wants — "Pro"
 * would need to be claimed once, for one model, in the whole catalog.
 *
 * Rule: slugify the name; if the result already starts with the title
 * slug (as either an exact match or a hyphen-separated prefix), use it
 * verbatim; otherwise prefix ``{titleSlug}-``.
 *
 * The empty name yields the empty string (so the field isn't prefilled
 * with just the title slug + trailing hyphen).
 */

import { slugifyForCatalog } from '$lib/create-form';

export function slugifyForModel(name: string, titleSlug: string): string {
	const base = slugifyForCatalog(name);
	if (!base) return '';
	if (base === titleSlug || base.startsWith(`${titleSlug}-`)) return base;
	return `${titleSlug}-${base}`;
}
