import { describe, expect, it } from 'vitest';

import { matchDetailSubroute } from './detail-subroute-match';

describe('matchDetailSubroute', () => {
	it('returns the subroute segment of /:entity/:slug/:subroute', () => {
		expect(matchDetailSubroute('/titles/medieval-madness/edit-history')).toBe('edit-history');
		expect(matchDetailSubroute('/titles/medieval-madness/sources')).toBe('sources');
		expect(matchDetailSubroute('/manufacturers/williams/edit')).toBe('edit');
		expect(matchDetailSubroute('/models/attack-from-mars/media')).toBe('media');
	});

	it('returns the subroute when extra segments follow', () => {
		expect(matchDetailSubroute('/models/attack-from-mars/edit/overview')).toBe('edit');
		expect(matchDetailSubroute('/manufacturers/williams/media/upload')).toBe('media');
	});

	it('returns null when there is no slug', () => {
		expect(matchDetailSubroute('/titles')).toBeNull();
		expect(matchDetailSubroute('/')).toBeNull();
		expect(matchDetailSubroute('')).toBeNull();
	});

	it('returns null when only entity + slug are present (no subroute)', () => {
		expect(matchDetailSubroute('/titles/medieval-madness')).toBeNull();
		expect(matchDetailSubroute('/titles/sources')).toBeNull();
		expect(matchDetailSubroute('/titles/edit-history')).toBeNull();
		expect(matchDetailSubroute('/titles/edit')).toBeNull();
	});

	it('ignores trailing slash', () => {
		expect(matchDetailSubroute('/titles/medieval-madness/edit/')).toBe('edit');
	});
});
