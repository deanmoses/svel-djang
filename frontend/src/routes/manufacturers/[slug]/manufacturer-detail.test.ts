import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { load } from './+layout.server';

const MOCK_MANUFACTURER = {
	name: 'Williams',
	slug: 'williams',
	description: { text: '', html: '', citations: [], attribution: null },
	year_start: 1985,
	year_end: 1999,
	country: null,
	headquarters: null,
	logo_url: null,
	website: '',
	entities: [
		{
			name: 'Williams Electronics',
			slug: 'williams-electronics',
			year_start: 1985,
			year_end: 1999,
			locations: []
		}
	],
	titles: [
		{
			name: 'Medieval Madness',
			slug: 'medieval-madness',
			year: 1997,
			thumbnail_url: null
		}
	],
	systems: [],
	persons: [],
	uploaded_media: [],
	sources: []
};

describe('manufacturer detail SSR route', () => {
	it('loads the manufacturer from the page endpoint', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify(MOCK_MANUFACTURER), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		const result = await load({
			fetch,
			url: new URL('http://localhost:5173/manufacturers/williams'),
			params: { slug: 'williams' }
		} as unknown as Parameters<typeof load>[0]);

		expect(result).toEqual({ manufacturer: MOCK_MANUFACTURER });
		const request = fetch.mock.calls[0]?.[0];
		expect(request).toBeInstanceOf(Request);
		expect(request.url).toBe('http://localhost:5173/api/pages/manufacturer/williams');
	});

	it('throws 404 when the manufacturer is not found', async () => {
		const fetch = vi.fn().mockResolvedValue(new Response('Not found', { status: 404 }));

		await expect(
			load({
				fetch,
				url: new URL('http://localhost:5173/manufacturers/nonexistent'),
				params: { slug: 'nonexistent' }
			} as unknown as Parameters<typeof load>[0])
		).rejects.toMatchObject({ status: 404 });
	});

	it('renders meaningful manufacturer content into initial HTML', () => {
		const { body } = render(Page, {
			props: {
				data: { manufacturer: MOCK_MANUFACTURER }
			}
		});

		expect(body).toContain('Medieval Madness');
	});
});
