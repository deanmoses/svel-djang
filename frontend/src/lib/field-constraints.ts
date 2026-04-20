/**
 * Fetch numeric field constraints from the backend.
 *
 * The backend derives these from Django model validators, making it the
 * single source of truth for min/max/step on numeric fields.
 */

import client from '$lib/api/client';
import type { CatalogEntityKey } from '$lib/api/catalog-meta';

export type FieldConstraint = {
	min?: number;
	max?: number;
	step?: number;
};

export type FieldConstraints = Record<string, FieldConstraint>;

const cache = new Map<string, FieldConstraints>();

export async function fetchFieldConstraints(
	entityType: CatalogEntityKey
): Promise<FieldConstraints> {
	const cached = cache.get(entityType);
	if (cached) return cached;

	const { data } = await client.GET('/api/field-constraints/{entity_type}', {
		params: { path: { entity_type: entityType } }
	});

	const constraints: FieldConstraints = (data as unknown as FieldConstraints) ?? {};
	cache.set(entityType, constraints);
	return constraints;
}

/** Get constraint props for a NumberField, suitable for spreading: `{...fc('year')}` */
export function fc(constraints: FieldConstraints, field: string): FieldConstraint {
	return constraints[field] ?? {};
}
