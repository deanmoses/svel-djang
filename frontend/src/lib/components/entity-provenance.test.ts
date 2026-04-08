import { describe, expect, it } from 'vitest';

import { groupSourcesByField } from './entity-provenance';

describe('groupSourcesByField', () => {
	it('separates conflicts, agreement, and single-source fields', () => {
		const result = groupSourcesByField([
			{
				field_name: 'year',
				value: 1997,
				source_name: 'IPDB',
				source_slug: 'ipdb',
				user_display: null,
				citation: '',
				created_at: '2026-04-08T00:00:00Z',
				is_winner: true,
				changeset_note: null
			},
			{
				field_name: 'year',
				value: 1998,
				source_name: 'OPDB',
				source_slug: 'opdb',
				user_display: null,
				citation: '',
				created_at: '2026-04-07T00:00:00Z',
				is_winner: false,
				changeset_note: null
			},
			{
				field_name: 'description',
				value: 'Updated copy',
				source_name: null,
				source_slug: null,
				user_display: 'editor',
				citation: '',
				created_at: '2026-04-08T00:00:00Z',
				is_winner: true,
				changeset_note: null
			},
			{
				field_name: 'description',
				value: 'Updated copy',
				source_name: 'IPDB',
				source_slug: 'ipdb',
				user_display: null,
				citation: '',
				created_at: '2026-04-07T00:00:00Z',
				is_winner: false,
				changeset_note: null
			},
			{
				field_name: 'manufacturer',
				value: 'Williams',
				source_name: 'IPDB',
				source_slug: 'ipdb',
				user_display: null,
				citation: '',
				created_at: '2026-04-07T00:00:00Z',
				is_winner: true,
				changeset_note: null
			}
		]);

		expect(result.conflicts.map((group) => group.field)).toEqual(['year']);
		expect(result.agreed.map((group) => group.field)).toEqual(['description']);
		expect(result.single.map((group) => group.field)).toEqual(['manufacturer']);
	});
});
