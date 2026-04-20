import { describe, expect, it } from 'vitest';

import { slugifyForModel } from './model-create';

describe('slugifyForModel', () => {
	it('prefixes the title slug when the name does not already contain it', () => {
		expect(slugifyForModel('Pro', 'godzilla')).toBe('godzilla-pro');
		expect(slugifyForModel('Premium LE', 'godzilla')).toBe('godzilla-premium-le');
	});

	it('leaves the slug verbatim when the name already starts with the title', () => {
		expect(slugifyForModel('Godzilla Pro', 'godzilla')).toBe('godzilla-pro');
	});

	it('uses the base as-is when it exactly equals the title slug', () => {
		// Rare — the "base" model for a title, bearing the title's own slug.
		expect(slugifyForModel('Godzilla', 'godzilla')).toBe('godzilla');
	});

	it('returns the empty string when the name has no alphanumerics', () => {
		// Prevents a dangling "godzilla-" prefix while the user is still typing.
		expect(slugifyForModel('', 'godzilla')).toBe('');
		expect(slugifyForModel('   ', 'godzilla')).toBe('');
		expect(slugifyForModel('!!!', 'godzilla')).toBe('');
	});

	it('does not treat a title-slug substring as a prefix match', () => {
		// "god" is a prefix of "godzilla", but we compare against the full title
		// slug with hyphen boundary.
		expect(slugifyForModel('Pro', 'god')).toBe('god-pro');
		expect(slugifyForModel('godspeed', 'god')).toBe('god-godspeed');
	});

	it('handles multi-word title slugs correctly', () => {
		expect(slugifyForModel('Pro', 'attack-from-mars')).toBe('attack-from-mars-pro');
		expect(slugifyForModel('Attack from Mars Remake', 'attack-from-mars')).toBe(
			'attack-from-mars-remake'
		);
	});
});
