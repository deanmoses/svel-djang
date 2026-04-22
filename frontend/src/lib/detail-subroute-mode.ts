import { matchDetailSubroute } from './detail-subroute-match';

export type DetailSubrouteMode = 'detail' | 'edit' | 'media' | 'sources' | 'edit-history';

export function resolveDetailSubrouteMode(pathname: string): DetailSubrouteMode {
	const subroute = matchDetailSubroute(pathname);
	switch (subroute) {
		case 'edit-history':
			return 'edit-history';
		case 'sources':
			return 'sources';
		case 'media':
			return 'media';
		case 'edit':
			return 'edit';
		default:
			return 'detail';
	}
}
