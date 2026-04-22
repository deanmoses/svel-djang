import { describe, expect, it } from 'vitest';

import { resolveDetailSubrouteMode } from './detail-subroute-mode';

describe('resolveDetailSubrouteMode', () => {
	it('returns detail for the base reader route', () => {
		expect(resolveDetailSubrouteMode('/manufacturers/williams')).toBe('detail');
	});

	it('returns edit for the edit route', () => {
		expect(resolveDetailSubrouteMode('/manufacturers/williams/edit')).toBe('edit');
	});

	it('returns edit for nested edit routes', () => {
		expect(resolveDetailSubrouteMode('/models/attack-from-mars/edit/overview')).toBe('edit');
	});

	it('returns media for the media route', () => {
		expect(resolveDetailSubrouteMode('/models/attack-from-mars/media')).toBe('media');
	});

	it('returns media for nested media routes', () => {
		expect(resolveDetailSubrouteMode('/manufacturers/williams/media/upload')).toBe('media');
	});

	it('returns sources for the sources route', () => {
		expect(resolveDetailSubrouteMode('/titles/medieval-madness/sources')).toBe('sources');
	});

	it('returns edit-history for the edit history route', () => {
		expect(resolveDetailSubrouteMode('/titles/medieval-madness/edit-history')).toBe('edit-history');
	});

	it('returns detail when slug happens to be "sources"', () => {
		// /titles/sources is a detail page for a title with slug='sources',
		// not the sources audit route — guards against the includes()-based
		// classifier bug.
		expect(resolveDetailSubrouteMode('/titles/sources')).toBe('detail');
	});

	it('returns detail when slug happens to be "edit-history"', () => {
		expect(resolveDetailSubrouteMode('/titles/edit-history')).toBe('detail');
	});

	it('returns detail when slug happens to be "edit"', () => {
		expect(resolveDetailSubrouteMode('/titles/edit')).toBe('detail');
	});

	it('returns detail when slug happens to be "media"', () => {
		expect(resolveDetailSubrouteMode('/titles/media')).toBe('detail');
	});
});
