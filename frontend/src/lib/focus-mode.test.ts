import { describe, expect, it } from 'vitest';

import { isFocusModePath } from './focus-mode';

describe('isFocusModePath', () => {
	describe('focus-mode routes', () => {
		it('matches top-level create', () => {
			expect(isFocusModePath('/titles/new')).toBe(true);
		});

		it('matches nested create', () => {
			expect(isFocusModePath('/titles/medieval-madness/models/new')).toBe(true);
		});

		it('matches edit without section', () => {
			expect(isFocusModePath('/manufacturers/williams/edit')).toBe(true);
		});

		it('matches edit with trailing slash', () => {
			expect(isFocusModePath('/manufacturers/williams/edit/')).toBe(true);
		});

		it('matches edit with section', () => {
			expect(isFocusModePath('/models/attack-from-mars/edit/overview')).toBe(true);
		});

		it('matches delete confirmation', () => {
			expect(isFocusModePath('/titles/medieval-madness/delete')).toBe(true);
		});

		it('matches edit-history', () => {
			expect(isFocusModePath('/titles/medieval-madness/edit-history')).toBe(true);
		});

		it('matches sources', () => {
			expect(isFocusModePath('/titles/medieval-madness/sources')).toBe(true);
		});
	});

	describe('full-chrome routes', () => {
		it('does not match the home page', () => {
			expect(isFocusModePath('/')).toBe(false);
		});

		it('does not match an entity index', () => {
			expect(isFocusModePath('/titles')).toBe(false);
		});

		it('does not match a detail page', () => {
			expect(isFocusModePath('/manufacturers/williams')).toBe(false);
		});

		it('does not match a detail subroute', () => {
			expect(isFocusModePath('/manufacturers/williams/media')).toBe(false);
		});

		it('does not match an entity record whose slug is "delete"', () => {
			// /:entity/delete is the detail page for a record with slug='delete',
			// not a delete-confirmation route.
			expect(isFocusModePath('/titles/delete')).toBe(false);
		});

		it('does not match an entity record whose slug is "edit"', () => {
			expect(isFocusModePath('/titles/edit')).toBe(false);
		});

		it('does not match "new" appearing mid-path', () => {
			expect(isFocusModePath('/titles/new/something')).toBe(false);
		});

		it('does not match "delete" appearing mid-path', () => {
			expect(isFocusModePath('/titles/medieval-madness/delete/extra')).toBe(false);
		});

		it('does not match an entity record whose slug is "sources"', () => {
			expect(isFocusModePath('/titles/sources')).toBe(false);
		});

		it('does not match an entity record whose slug is "edit-history"', () => {
			expect(isFocusModePath('/titles/edit-history')).toBe(false);
		});

		it('does not match "sources" with trailing extra segments', () => {
			expect(isFocusModePath('/titles/medieval-madness/sources/something')).toBe(false);
		});

		it('does not match "edit-history" with trailing extra segments', () => {
			expect(isFocusModePath('/titles/medieval-madness/edit-history/something')).toBe(false);
		});
	});
});
