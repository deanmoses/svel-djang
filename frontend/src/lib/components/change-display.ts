import type { components } from '$lib/api/schema';

type FieldChange = components['schemas']['FieldChangeSchema'];

/**
 * Type guard: true when both old and new values are strings and at least one
 * exceeds 80 characters, meaning the change should render as an InlineDiff
 * rather than a simple old → new display.
 */
export function isDiffable(
	change: FieldChange
): change is FieldChange & { old_value: string; new_value: string } {
	return (
		typeof change.old_value === 'string' &&
		typeof change.new_value === 'string' &&
		(change.old_value.length > 80 || change.new_value.length > 80)
	);
}

/** Format an unknown claim value for inline display, with truncation. */
export function formatValue(v: unknown): string {
	if (v === null || v === undefined || v === '') return '\u2014';
	const s = typeof v === 'string' ? v : JSON.stringify(v);
	return s.length > 120 ? s.slice(0, 120) + '...' : s;
}
