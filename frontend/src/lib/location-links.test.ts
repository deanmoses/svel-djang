import { describe, expect, it } from 'vitest';
import { buildLocationParts } from './location-links';

describe('buildLocationParts', () => {
	it('returns leaf plus ancestors using display_name', () => {
		expect(
			buildLocationParts({
				location_path: 'usa/il/chicago',
				location_type: 'city',
				display_name: 'Chicago',
				slug: 'chicago',
				ancestors: [
					{ display_name: 'Illinois', location_path: 'usa/il' },
					{ display_name: 'USA', location_path: 'usa' }
				]
			})
		).toEqual([
			{ text: 'Chicago', href: '/locations/usa/il/chicago' },
			{ text: 'Illinois', href: '/locations/usa/il' },
			{ text: 'USA', href: '/locations/usa' }
		]);
	});

	it('returns just the leaf when there are no ancestors', () => {
		expect(
			buildLocationParts({
				location_path: 'italy',
				location_type: 'country',
				display_name: 'Italy',
				slug: 'italy',
				ancestors: []
			})
		).toEqual([{ text: 'Italy', href: '/locations/italy' }]);
	});
});
