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
