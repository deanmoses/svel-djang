import { getContext, setContext } from 'svelte';

/**
 * Context exposed by every entity `[slug]/+layout.svelte` so descendant
 * routes (audit pages, focus shells, etc.) can read the entity's display
 * name and detail URL without coupling to the loader's data-key (which
 * varies across entities: `data.title`, `data.profile`, `data.model`, …).
 *
 * Callers should pass an object whose properties are getters so values
 * stay reactive across navigation (e.g. `/titles/A/sources` → `/titles/B/sources`
 * must re-read `title.name`).
 */
export type EntityContext = {
	readonly name: string;
	readonly detailHref: string;
};

const ENTITY_CONTEXT_KEY = Symbol('entity');

export function setEntityContext(context: EntityContext): void {
	setContext(ENTITY_CONTEXT_KEY, context);
}

export function getEntityContext(): EntityContext {
	const context = getContext<EntityContext | undefined>(ENTITY_CONTEXT_KEY);
	if (!context) {
		throw new Error('entity context missing — must be rendered inside an entity [slug] layout');
	}
	return context;
}
