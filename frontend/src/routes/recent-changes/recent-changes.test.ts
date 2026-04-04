import { describe, expect, it } from 'vitest';
import { changesLabel } from './recent-changes';

describe('changesLabel', () => {
	it('singularizes "change" for count of 1', () => {
		expect(changesLabel({ changes_count: 1, retractions_count: 0 })).toBe('1 change');
	});

	it('pluralizes "changes" for count > 1', () => {
		expect(changesLabel({ changes_count: 5, retractions_count: 0 })).toBe('5 changes');
	});

	it('handles zero changes', () => {
		expect(changesLabel({ changes_count: 0, retractions_count: 0 })).toBe('0 changes');
	});

	it('appends singular retraction suffix', () => {
		expect(changesLabel({ changes_count: 3, retractions_count: 1 })).toBe(
			'3 changes including 1 retraction'
		);
	});

	it('appends plural retractions suffix', () => {
		expect(changesLabel({ changes_count: 5, retractions_count: 2 })).toBe(
			'5 changes including 2 retractions'
		);
	});

	it('omits retraction suffix when retractions_count is 0', () => {
		expect(changesLabel({ changes_count: 4, retractions_count: 0 })).not.toContain('retraction');
	});
});
