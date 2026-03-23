import { describe, expect, it } from 'vitest';
import { buildLocationParts } from './location-links';

describe('buildLocationParts', () => {
	it('links stateless cities through the country city route', () => {
		expect(
			buildLocationParts({
				city: 'Bologna',
				state: '',
				country: 'Italy',
				city_slug: 'bologna',
				state_slug: '',
				country_slug: 'italy'
			})
		).toEqual([
			{ text: 'Bologna', href: '/locations/italy/cities/bologna' },
			{ text: 'Italy', href: '/locations/italy' }
		]);
	});

	it('links stateful cities through the state city route', () => {
		expect(
			buildLocationParts({
				city: 'Chicago',
				state: 'Illinois',
				country: 'USA',
				city_slug: 'chicago',
				state_slug: 'illinois',
				country_slug: 'usa'
			})
		).toEqual([
			{ text: 'Chicago', href: '/locations/usa/illinois/chicago' },
			{ text: 'Illinois', href: '/locations/usa/illinois' },
			{ text: 'USA', href: '/locations/usa' }
		]);
	});
});
