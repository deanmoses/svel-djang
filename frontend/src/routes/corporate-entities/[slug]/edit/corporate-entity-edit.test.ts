import { describe, expect, it } from 'vitest';

import {
	buildCorporateEntityPatchBody,
	corporateEntityToFormFields,
	type CorporateEntityEditState,
	type CorporateEntityFormFields
} from './corporate-entity-edit';

const baseEntity = {
	slug: 'williams-electronics-games',
	name: 'Williams Electronics Games',
	description: { text: 'Corporate era.' },
	year_start: 1985,
	year_end: 1999,
	aliases: ['Williams Games', 'WEG']
};

function stateFromEntity(overrides?: Partial<CorporateEntityEditState>): CorporateEntityEditState {
	return {
		fields: corporateEntityToFormFields(baseEntity),
		aliases: [...(baseEntity.aliases ?? [])],
		...overrides
	};
}

describe('corporateEntityToFormFields', () => {
	it('maps nullable values to editable form fields', () => {
		expect(
			corporateEntityToFormFields({
				...baseEntity,
				description: null,
				year_start: null,
				year_end: null
			})
		).toEqual({
			slug: 'williams-electronics-games',
			name: 'Williams Electronics Games',
			description: '',
			year_start: '',
			year_end: ''
		});
	});
});

describe('buildCorporateEntityPatchBody', () => {
	it('returns null when nothing changed', () => {
		expect(buildCorporateEntityPatchBody(stateFromEntity(), baseEntity)).toBeNull();
	});

	it('builds a payload for scalar and alias changes', () => {
		const fields: CorporateEntityFormFields = {
			...corporateEntityToFormFields(baseEntity),
			year_end: 2000
		};

		expect(
			buildCorporateEntityPatchBody(
				stateFromEntity({
					fields,
					aliases: ['WMS Games']
				}),
				baseEntity
			)
		).toEqual({
			fields: { year_end: 2000 },
			aliases: ['WMS Games']
		});
	});

	it('includes slug changes in the scalar payload', () => {
		const fields: CorporateEntityFormFields = {
			...corporateEntityToFormFields(baseEntity),
			slug: 'williams-games'
		};

		expect(buildCorporateEntityPatchBody(stateFromEntity({ fields }), baseEntity)).toEqual({
			fields: { slug: 'williams-games' },
			aliases: null
		});
	});

	it('maps cleared numeric fields to null', () => {
		const fields: CorporateEntityFormFields = {
			...corporateEntityToFormFields(baseEntity),
			year_end: NaN
		};

		expect(buildCorporateEntityPatchBody(stateFromEntity({ fields }), baseEntity)).toEqual({
			fields: { year_end: null },
			aliases: null
		});
	});

	it('treats alias reordering as unchanged', () => {
		expect(
			buildCorporateEntityPatchBody(
				stateFromEntity({ aliases: ['WEG', 'Williams Games'] }),
				baseEntity
			)
		).toBeNull();
	});
});
