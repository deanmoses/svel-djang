import { render } from 'svelte/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { pageState } = vi.hoisted(() => ({
	pageState: {
		params: { slug: 'williams' },
		url: new URL('http://localhost:5173/manufacturers/williams')
	}
}));

vi.mock('$app/state', () => ({
	page: pageState
}));

import Harness from './layout.test-harness.svelte';

const MOCK_MANUFACTURER = {
	name: 'Williams',
	slug: 'williams',
	description: {
		text: 'Historic manufacturer [1].',
		html: '<p>Historic manufacturer.</p>',
		citations: [],
		attribution: null
	},
	year_start: 1985,
	year_end: 1999,
	country: null,
	headquarters: null,
	logo_url: null,
	website: 'https://williams.example',
	entities: [
		{
			name: 'Williams Electronics',
			slug: 'williams-electronics',
			year_start: 1985,
			year_end: 1999,
			locations: []
		}
	],
	titles: [],
	systems: [],
	persons: [],
	uploaded_media: [],
	sources: []
};

describe('manufacturer layout', () => {
	beforeEach(() => {
		pageState.params.slug = 'williams';
		pageState.url = new URL('http://localhost:5173/manufacturers/williams');
	});

	it('renders the action bar without the legacy tab navigation on the detail route', () => {
		const { body } = render(Harness, {
			props: { data: { manufacturer: MOCK_MANUFACTURER } }
		});

		expect(body).toContain('History');
		expect(body).not.toContain('>Back<');
		expect(body).not.toContain('Page sections');
	});

	it('renders a Back link on media subroutes', () => {
		pageState.url = new URL('http://localhost:5173/manufacturers/williams/media');

		const { body } = render(Harness, {
			props: { data: { manufacturer: MOCK_MANUFACTURER } }
		});

		expect(body).toContain('>Back<');
		expect(body).toContain('/manufacturers/williams');
	});
});
