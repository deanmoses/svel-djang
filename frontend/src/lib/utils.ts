import { resolve } from '$app/paths';

/** Normalize text for search: strip diacritics, punctuation, and collapse whitespace. */
export function normalizeText(s: string): string {
	return s
		.normalize('NFD')
		.replace(/[\u0300-\u036f]/g, '') // strip diacritics
		.replace(/[^\w\s]/g, '') // strip punctuation
		.replace(/\s+/g, ' ') // collapse whitespace
		.trim()
		.toLowerCase();
}

/** Wrapper around resolve() that accepts a plain string (for dynamic URLs). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const resolveHref = (url: string) => resolve(url as any);

/** Format a count with a singular/plural noun. `pluralize(1, 'model')` → `'1 model'`. */
export function pluralize(n: number, one: string, many?: string): string {
	return `${n} ${n === 1 ? one : (many ?? `${one}s`)}`;
}

/** Format a year_start / year_end pair as a human-readable range. */
export function formatYearRange(yearStart?: number | null, yearEnd?: number | null): string | null {
	if (yearStart && yearEnd) return `${yearStart}\u2013${yearEnd}`;
	if (yearStart) return `${yearStart}\u2013present`;
	if (yearEnd) return `\u2013${yearEnd}`;
	return null;
}

export function websiteHostname(url: string): string {
	try {
		return new URL(url).hostname;
	} catch {
		return url;
	}
}
