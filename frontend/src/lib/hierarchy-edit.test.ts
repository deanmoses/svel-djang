import { describe, expect, it } from 'vitest';

import {
	buildHierarchyPatchBody,
	hierarchyToFormFields,
	type HierarchyEditState,
	type HierarchyEditView
} from './hierarchy-edit';

const baseEntity: HierarchyEditView = {
	name: 'Sports',
	description: { text: 'Athletic themes.' },
	parents: [{ slug: 'competition' }],
	aliases: ['Athletics', 'Sport']
};

function stateFromEntity(
	entity: HierarchyEditView,
	overrides?: Partial<HierarchyEditState>
): HierarchyEditState {
	return {
		fields: hierarchyToFormFields(entity),
		parents: (entity.parents ?? []).map((p) => p.slug),
		aliases: [...(entity.aliases ?? [])],
		...overrides
	};
}

describe('hierarchyToFormFields', () => {
	it('converts entity to form state', () => {
		expect(hierarchyToFormFields(baseEntity)).toEqual({
			name: 'Sports',
			description: 'Athletic themes.'
		});
	});

	it('handles missing description', () => {
		expect(hierarchyToFormFields({ ...baseEntity, description: null }).description).toBe('');
	});
});

describe('buildHierarchyPatchBody — no-op', () => {
	it('returns null when nothing changed', () => {
		expect(buildHierarchyPatchBody(stateFromEntity(baseEntity), baseEntity)).toBeNull();
	});
});

describe('buildHierarchyPatchBody — scalars', () => {
	it('detects changed name', () => {
		const fields = { ...hierarchyToFormFields(baseEntity), name: 'Updated Sports' };
		const body = buildHierarchyPatchBody(stateFromEntity(baseEntity, { fields }), baseEntity)!;
		expect(body.fields).toEqual({ name: 'Updated Sports' });
		expect(body.parents).toBeNull();
		expect(body.aliases).toBeNull();
	});

	it('sends null for cleared description', () => {
		const fields = { ...hierarchyToFormFields(baseEntity), description: '' };
		const body = buildHierarchyPatchBody(stateFromEntity(baseEntity, { fields }), baseEntity)!;
		expect(body.fields.description).toBeNull();
	});
});

describe('buildHierarchyPatchBody — parents', () => {
	it('detects added parent', () => {
		const state = stateFromEntity(baseEntity, { parents: ['competition', 'outdoor'] });
		const body = buildHierarchyPatchBody(state, baseEntity)!;
		expect(body.parents).toEqual(['competition', 'outdoor']);
	});

	it('detects cleared parents', () => {
		const state = stateFromEntity(baseEntity, { parents: [] });
		const body = buildHierarchyPatchBody(state, baseEntity)!;
		expect(body.parents).toEqual([]);
	});

	it('ignores reordering', () => {
		const entity: HierarchyEditView = {
			...baseEntity,
			parents: [{ slug: 'a' }, { slug: 'b' }]
		};
		const state = stateFromEntity(entity, { parents: ['b', 'a'] });
		expect(buildHierarchyPatchBody(state, entity)).toBeNull();
	});
});

describe('buildHierarchyPatchBody — aliases', () => {
	it('detects added alias', () => {
		const state = stateFromEntity(baseEntity, {
			aliases: ['Athletics', 'Sport', 'Sporting']
		});
		const body = buildHierarchyPatchBody(state, baseEntity)!;
		expect(body.aliases).toEqual(['Athletics', 'Sport', 'Sporting']);
	});

	it('detects removed alias', () => {
		const state = stateFromEntity(baseEntity, { aliases: ['Athletics'] });
		const body = buildHierarchyPatchBody(state, baseEntity)!;
		expect(body.aliases).toEqual(['Athletics']);
	});

	it('detects cleared aliases', () => {
		const state = stateFromEntity(baseEntity, { aliases: [] });
		const body = buildHierarchyPatchBody(state, baseEntity)!;
		expect(body.aliases).toEqual([]);
	});
});

describe('buildHierarchyPatchBody — mixed', () => {
	it('builds correct body with scalar + parent + alias changes', () => {
		const fields = { ...hierarchyToFormFields(baseEntity), description: 'New desc' };
		const state = stateFromEntity(baseEntity, {
			fields,
			parents: ['outdoor'],
			aliases: ['Athletics']
		});
		const body = buildHierarchyPatchBody(state, baseEntity)!;
		expect(body.fields).toEqual({ description: 'New desc' });
		expect(body.parents).toEqual(['outdoor']);
		expect(body.aliases).toEqual(['Athletics']);
	});
});
