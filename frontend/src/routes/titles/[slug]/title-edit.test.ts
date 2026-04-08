import { describe, expect, it } from 'vitest';

import { buildModelBoundary, buildTitlePatchBody, titleToFormState } from './title-edit';

const multiModelTitle = {
	slug: 'medieval-madness',
	name: 'Medieval Madness',
	description: { text: 'Castle bashers.' },
	franchise: { slug: 'castle-games', name: 'Castle Games' },
	abbreviations: ['MM'],
	machines: [
		{ slug: 'medieval-madness', name: 'Medieval Madness' },
		{ slug: 'medieval-madness-remake', name: 'Medieval Madness (Remake)' }
	],
	model_detail: null
};

const singleModelTitle = {
	slug: 'attack-from-mars',
	name: 'Attack from Mars',
	description: { text: 'Martians.' },
	franchise: null,
	abbreviations: ['AFM'],
	machines: [{ slug: 'attack-from-mars', name: 'Attack from Mars' }],
	model_detail: { slug: 'attack-from-mars' }
};

const titleWithVariants = {
	slug: 'the-addams-family',
	name: 'The Addams Family',
	description: { text: 'Snap snap.' },
	franchise: null,
	abbreviations: ['TAF'],
	machines: [
		{
			slug: 'the-addams-family',
			name: 'The Addams Family',
			variants: [{ slug: 'the-addams-family-gold', name: 'The Addams Family Gold' }]
		}
	],
	model_detail: null
};

describe('titleToFormState', () => {
	it('loads current title values into editable form state', () => {
		expect(titleToFormState(multiModelTitle)).toEqual({
			slug: 'medieval-madness',
			name: 'Medieval Madness',
			description: 'Castle bashers.',
			franchiseSlug: 'castle-games',
			abbreviationsText: 'MM'
		});
	});
});

describe('buildTitlePatchBody', () => {
	it('builds the expected PATCH payload for fields and abbreviations', () => {
		const body = buildTitlePatchBody(
			{
				slug: 'medieval-madness-remastered',
				name: 'Medieval Madness Remastered',
				description: 'Updated title copy',
				franchiseSlug: '',
				abbreviationsText: 'MM, MMR'
			},
			multiModelTitle
		);

		expect(body).toEqual({
			fields: {
				slug: 'medieval-madness-remastered',
				name: 'Medieval Madness Remastered',
				description: 'Updated title copy',
				franchise: null
			},
			abbreviations: ['MM', 'MMR']
		});
	});

	it('returns null when nothing changed', () => {
		expect(buildTitlePatchBody(titleToFormState(multiModelTitle), multiModelTitle)).toBeNull();
	});
});

describe('buildModelBoundary', () => {
	it('shows direct model edit and sources links for single-model titles', () => {
		expect(buildModelBoundary(singleModelTitle)).toEqual({
			modelLinks: [],
			singleModelActions: {
				editHref: '/models/attack-from-mars/edit',
				sourcesHref: '/models/attack-from-mars/sources'
			}
		});
	});

	it('omits single-model actions for multi-model titles while keeping model links', () => {
		expect(buildModelBoundary(multiModelTitle)).toEqual({
			modelLinks: [
				{ slug: 'medieval-madness', name: 'Medieval Madness' },
				{ slug: 'medieval-madness-remake', name: 'Medieval Madness (Remake)' }
			],
			singleModelActions: null
		});
	});

	it('includes variant model links in the boundary section', () => {
		expect(buildModelBoundary(titleWithVariants)).toEqual({
			modelLinks: [
				{ slug: 'the-addams-family', name: 'The Addams Family' },
				{ slug: 'the-addams-family-gold', name: 'The Addams Family Gold' }
			],
			singleModelActions: null
		});
	});
});
