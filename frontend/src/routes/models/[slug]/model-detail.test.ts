import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { load } from './+layout.server';

const MOCK_MODEL = {
	name: 'Medieval Madness',
	slug: 'medieval-madness',
	year: 1997,
	month: null,
	manufacturer: { name: 'Williams', slug: 'williams' },
	corporate_entity: {
		name: 'Williams Electronics',
		slug: 'williams-electronics'
	},
	title: { name: 'Medieval Madness', slug: 'medieval-madness' },
	title_description: { text: '', html: '', attribution: null },
	description: { text: '', html: '', attribution: null },
	technology_generation: null,
	technology_subgeneration: null,
	display_type: null,
	display_subtype: null,
	system: null,
	cabinet: null,
	game_format: null,
	player_count: null,
	flipper_count: null,
	production_quantity: '',
	thumbnail_url: null,
	hero_image_url: null,
	image_attribution: null,
	ipdb_id: null,
	opdb_id: null,
	pinside_id: null,
	ipdb_rating: null,
	pinside_rating: null,
	website: '',
	variant_of: null,
	variants: [],
	variant_siblings: [],
	variant_features: [],
	converted_from: null,
	conversions: [],
	remake_of: null,
	remakes: [],
	themes: [],
	tags: [],
	gameplay_features: [],
	reward_types: [],
	abbreviations: [],
	extra_data: {},
	franchise: null,
	series: [],
	title_models: [],
	credits: [
		{
			person: { name: 'Pat Lawlor', slug: 'pat-lawlor' },
			role: 'designer',
			role_display: 'Designed',
			role_sort_order: 1
		}
	],
	uploaded_media: [],
	sources: []
};

describe('model detail SSR route', () => {
	it('loads the model from the page endpoint', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify(MOCK_MODEL), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		const result = await load({
			fetch,
			url: new URL('http://localhost:5173/models/medieval-madness'),
			params: { slug: 'medieval-madness' }
		} as unknown as Parameters<typeof load>[0]);

		expect(result).toEqual({ model: MOCK_MODEL });
		const request = fetch.mock.calls[0]?.[0];
		expect(request).toBeInstanceOf(Request);
		expect(request.url).toBe('http://localhost:5173/api/pages/model/medieval-madness');
	});

	it('throws 404 when the model is not found', async () => {
		const fetch = vi.fn().mockResolvedValue(new Response('Not found', { status: 404 }));

		await expect(
			load({
				fetch,
				url: new URL('http://localhost:5173/models/nonexistent'),
				params: { slug: 'nonexistent' }
			} as unknown as Parameters<typeof load>[0])
		).rejects.toMatchObject({ status: 404 });
	});

	it('renders meaningful model content into initial HTML', () => {
		const { body } = render(Page, {
			props: {
				data: { model: MOCK_MODEL }
			}
		});

		expect(body).toContain('Pat Lawlor');
	});
});
