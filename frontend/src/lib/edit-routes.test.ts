import { describe, expect, it } from 'vitest';

import { getEditRedirectHref } from './edit-routes';

describe('getEditRedirectHref', () => {
	it('returns null when the slug did not change', () => {
		expect(getEditRedirectHref('models', 'medieval-madness', 'medieval-madness')).toBeNull();
	});

	it('builds the edit href when the slug changed', () => {
		expect(getEditRedirectHref('models', 'medieval-madness', 'medieval-madness-remastered')).toBe(
			'/models/medieval-madness-remastered/edit'
		);
	});

	it('appends section segment when provided', () => {
		expect(
			getEditRedirectHref('models', 'medieval-madness', 'medieval-madness-remastered', 'basics')
		).toBe('/models/medieval-madness-remastered/edit/basics');
	});
});
