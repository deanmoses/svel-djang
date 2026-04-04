import { diffWordsWithSpace } from 'diff';

export type DiffSegment = {
	text: string;
	type: 'added' | 'removed' | 'unchanged';
};

/**
 * Compute a word-level diff between two strings.
 *
 * Uses diffWordsWithSpace (not diffWords) so whitespace-only changes
 * like added paragraph breaks are visible in the output.
 */
export function computeWordDiff(oldText: string, newText: string): DiffSegment[] {
	const changes = diffWordsWithSpace(oldText, newText);
	return changes.map((c) => ({
		text: c.value,
		type: c.added ? 'added' : c.removed ? 'removed' : 'unchanged'
	}));
}
