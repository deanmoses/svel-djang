import { render } from 'svelte/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { pageState, authState } = vi.hoisted(() => ({
	pageState: {
		params: { slug: 'medieval-madness' },
		url: new URL('http://localhost:5173/titles/medieval-madness')
	},
	authState: { isAuthenticated: false }
}));

vi.mock('$app/state', () => ({
	page: pageState
}));

vi.mock('$lib/auth.svelte', () => ({
	auth: {
		get isAuthenticated() {
			return authState.isAuthenticated;
		},
		load: vi.fn()
	}
}));

import Harness from './layout.test-harness.svelte';

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
	series: null,
	credits: [],
	agreed_specs: { themes: [], gameplay_features: [], reward_types: [], tags: [] },
	related_titles: [],
	media: [],
	opdb_id: null,
	fandom_page_id: null,
	model_detail: null,
	sources: []
};

describe('title layout', () => {
	beforeEach(() => {
		pageState.params.slug = 'medieval-madness';
		pageState.url = new URL('http://localhost:5173/titles/medieval-madness');
		authState.isAuthenticated = false;
	});

	it('omits the Back link on the detail route', () => {
		const { body } = render(Harness, {
			props: { data: { title: MOCK_TITLE } }
		});

		expect(body).toContain('History');
		expect(body).not.toContain('>Back<');
	});

	it('renders a Back link on sources subroutes', () => {
		pageState.url = new URL('http://localhost:5173/titles/medieval-madness/sources');

		const { body } = render(Harness, {
			props: { data: { title: MOCK_TITLE } }
		});

		expect(body).toContain('>Back<');
		expect(body).toContain('/titles/medieval-madness');
	});

	it('renders direct edit links on editable title sidebar sections when authenticated', () => {
		authState.isAuthenticated = true;

		const { body } = render(Harness, {
			props: {
				data: {
					title: {
						...MOCK_TITLE,
						franchise: { name: 'Williams Classics', slug: 'williams-classics' }
					}
				}
			}
		});

		expect(body).toContain('Franchise');
		expect(body).toContain('>edit<');
	});
});
