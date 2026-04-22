import type { components } from '$lib/api/schema';

type ChangeSetSummary = components['schemas']['ChangeSetSummarySchema'];

/** Build a human-readable summary like "3 changes including 1 retraction". */
export function changesLabel(
	cs: Pick<ChangeSetSummary, 'changes_count' | 'retractions_count'>
): string {
	const n = cs.changes_count;
	let label = `${n} ${n === 1 ? 'change' : 'changes'}`;
	if (cs.retractions_count > 0) {
		label += ` including ${cs.retractions_count} ${cs.retractions_count === 1 ? 'retraction' : 'retractions'}`;
	}
	return label;
}
