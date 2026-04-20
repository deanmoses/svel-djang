export type DetailSubrouteMode = 'detail' | 'edit' | 'media' | 'sources' | 'edit-history';

function pathSegments(pathname: string): string[] {
	return pathname.split('/').filter(Boolean);
}

export function resolveDetailSubrouteMode(pathname: string): DetailSubrouteMode {
	const segments = pathSegments(pathname);

	if (segments.includes('edit-history')) return 'edit-history';
	if (segments.includes('sources')) return 'sources';
	if (segments.includes('media')) return 'media';
	if (segments.includes('edit')) return 'edit';
	return 'detail';
}
