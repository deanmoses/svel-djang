import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { load } from './+layout.server';

const MOCK_TITLE = {
	name: 'Medieval Madness',
	slug: 'medieval-madness',
	abbreviations: [],
	description: { text: '', html: '', citations: [], attribution: null },
	needs_review: false,
	needs_review_notes: '',
	review_links: [],
	hero_image_url: null,
	franchise: null,
	machines: [
		{
			name: 'Medieval Madness',
			slug: 'medieval-madness',
			year: 1997,
			manufacturer: { name: 'Williams', slug: 'williams' },
			technology_generation_name: 'Solid State',
			thumbnail_url: null,
			variants: []
		}
	],
	series: [],
	credits: [],
	agreed_specs: { themes: [], gameplay_features: [], reward_types: [] },
	model_detail: null,
	sources: []
};

describe('title detail SSR route', () => {
	it('loads the title from the page endpoint', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify(MOCK_TITLE), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		const result = await load({
			fetch,
			url: new URL('http://localhost:5173/titles/medieval-madness'),
			params: { slug: 'medieval-madness' }
		} as unknown as Parameters<typeof load>[0]);

		expect(result).toEqual({ title: MOCK_TITLE });
		const request = fetch.mock.calls[0]?.[0];
		expect(request).toBeInstanceOf(Request);
		expect(request.url).toBe('http://localhost:5173/api/pages/title/medieval-madness');
	});

	it('throws 404 when the title is not found', async () => {
		const fetch = vi.fn().mockResolvedValue(new Response('Not found', { status: 404 }));

		await expect(
			load({
				fetch,
				url: new URL('http://localhost:5173/titles/nonexistent'),
				params: { slug: 'nonexistent' }
			} as unknown as Parameters<typeof load>[0])
		).rejects.toMatchObject({ status: 404 });
	});

	it('renders meaningful title content into initial HTML', () => {
		const { body } = render(Page, {
			props: {
				data: { title: MOCK_TITLE }
			}
		});

		// The page renders a tab label showing the machine count, proving
		// backend data reached the server-rendered HTML.
		expect(body).toContain('Models (1)');
	});
});
