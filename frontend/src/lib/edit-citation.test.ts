import { describe, expect, it } from 'vitest';

import {
	buildEditCitationRequest,
	countPendingChanges,
	shouldShowMixedEditCitationWarning,
	withEditMetadata,
	type EditCitationSelection
} from './edit-citation';

const citation: EditCitationSelection = {
	citationInstanceId: 42,
	sourceName: 'Williams Flyer',
	locator: 'p. 2'
};

describe('buildEditCitationRequest', () => {
	it('serializes the selected citation instance id', () => {
		expect(buildEditCitationRequest(citation)).toEqual({
			citation_instance_id: 42
		});
	});

	it('omits citation when none is selected', () => {
		expect(buildEditCitationRequest(null)).toBeUndefined();
	});
});

describe('withEditMetadata', () => {
	it('adds trimmed note and citation to an existing patch body', () => {
		expect(
			withEditMetadata({ fields: { description: 'Updated' } }, '  cleanup  ', citation)
		).toEqual({
			fields: { description: 'Updated' },
			note: 'cleanup',
			citation: { citation_instance_id: 42 }
		});
	});

	it('preserves bodies without a citation', () => {
		expect(withEditMetadata({ fields: { description: 'Updated' } }, '', null)).toEqual({
			fields: { description: 'Updated' },
			note: ''
		});
	});
});

describe('countPendingChanges', () => {
	it('counts scalar field changes individually and relationship buckets once', () => {
		expect(
			countPendingChanges({
				fields: { year: 1998, description: 'Updated' },
				themes: ['medieval'],
				note: 'ignored',
				citation: { citation_instance_id: 42 }
			})
		).toBe(3);
	});

	it('returns zero for empty bodies', () => {
		expect(countPendingChanges(null)).toBe(0);
	});
});

describe('shouldShowMixedEditCitationWarning', () => {
	it('warns when one citation is attached to multiple pending changes', () => {
		expect(
			shouldShowMixedEditCitationWarning(
				{
					fields: { year: 1998, description: 'Updated' }
				},
				citation
			)
		).toBe(true);
	});

	it('does not warn for a single pending change or no citation', () => {
		expect(
			shouldShowMixedEditCitationWarning(
				{
					fields: { description: 'Updated' }
				},
				citation
			)
		).toBe(false);
		expect(
			shouldShowMixedEditCitationWarning(
				{
					fields: { description: 'Updated', year: 1998 }
				},
				null
			)
		).toBe(false);
	});
});
