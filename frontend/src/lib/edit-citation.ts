export type EditCitationSelection = {
	citationInstanceId: number;
	sourceName: string;
	locator: string;
};

export type EditCitationRequest = {
	citation_instance_id: number;
};

type PatchBody = Record<string, unknown>;

export function buildEditCitationRequest(
	citation: EditCitationSelection | null
): EditCitationRequest | undefined {
	if (!citation) return undefined;
	return { citation_instance_id: citation.citationInstanceId };
}

export function withEditMetadata<T extends PatchBody>(
	body: T,
	note: string,
	citation: EditCitationSelection | null
): T & { note: string; citation?: EditCitationRequest } {
	const citationRequest = buildEditCitationRequest(citation);
	return {
		...body,
		note: note.trim(),
		...(citationRequest ? { citation: citationRequest } : {})
	};
}

export function countPendingChanges(body: PatchBody | null): number {
	if (!body) return 0;

	let count = 0;
	for (const [key, value] of Object.entries(body)) {
		if (key === 'note' || key === 'citation' || value == null) continue;

		if (key === 'fields' && typeof value === 'object' && !Array.isArray(value)) {
			count += Object.keys(value as Record<string, unknown>).length;
			continue;
		}

		count += 1;
	}

	return count;
}

export function shouldShowMixedEditCitationWarning(
	body: PatchBody | null,
	citation: EditCitationSelection | null
): boolean {
	return citation !== null && countPendingChanges(body) > 1;
}
