import type { components } from '$lib/api/schema';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CitationSourceResult = components['schemas']['CitationSourceSearchSchema'];
export type ChildSource = components['schemas']['CitationSourceChildSchema'];

/** Subset of a search result carried through the state machine after selecting an abstract source. */
export type ParentContext = {
	id: number;
	name: string;
	source_type: string;
	author: string;
	child_input_mode: string | null;
	/** Stable key for identifier parsing dispatch. Pending backend model field. */
	identifier_key: string | null;
};

/** An unsaved draft of a CitationInstance.  Accumulates across stages: search sets sourceId, identify may change it, locator sets locator. */
export type CitationInstanceDraft = {
	sourceId: number | null;
	sourceName: string;
	locator: string;
	skipLocator: boolean;
};

/** Which stage the citation flow is in. Each variant carries only the context that stage needs. */
export type CiteState =
	| { stage: 'search'; draft: CitationInstanceDraft }
	| {
			stage: 'identify';
			draft: CitationInstanceDraft;
			parent: ParentContext;
			prefillIdentifier?: string;
	  }
	| {
			stage: 'create';
			draft: CitationInstanceDraft;
			parent: ParentContext | null;
			prefillName: string;
	  }
	| { stage: 'locator'; draft: CitationInstanceDraft };

/** Inputs to the state machine, dispatched by stage components via the orchestrator. */
export type CiteAction =
	| { type: 'select_source'; source: CitationSourceResult }
	| { type: 'select_source_with_id'; source: CitationSourceResult; identifier: string }
	| { type: 'select_child'; sourceId: number; sourceName: string; skipLocator: boolean }
	| { type: 'start_create'; prefillName: string }
	| { type: 'created'; sourceId: number; sourceName: string; skipLocator: boolean };

// ---------------------------------------------------------------------------
// Pure functions
// ---------------------------------------------------------------------------

export function suppressChildResults(results: CitationSourceResult[]): CitationSourceResult[] {
	const resultIds = new Set(results.map((r) => r.id));
	return results.filter((r) => !r.parent_id || !resultIds.has(r.parent_id));
}

const IPDB_RE = /^https?:\/\/(?:www\.)?ipdb\.org\/machine\.cgi\?id=(\d+)/;
const OPDB_RE = /^https?:\/\/(?:www\.)?opdb\.org\/machines\/([A-Za-z0-9_-]+)/;

/** Pre-selection: matches a pasted URL before any source is selected. */
export function detectSourceFromUrl(url: string): { sourceName: string; machineId: string } | null {
	let match = IPDB_RE.exec(url);
	if (match) return { sourceName: 'IPDB', machineId: match[1] };

	match = OPDB_RE.exec(url);
	if (match) return { sourceName: 'OPDB', machineId: match[1] };

	return null;
}

const BARE_DIGITS = /^\d+$/;
const BARE_OPDB_ID = /^[A-Za-z0-9_-]+$/;

/** Post-selection: dispatches on a backend-provided key, not display names. */
export function parseIdentifierInput(identifierKey: string | null, input: string): string | null {
	if (!input || !identifierKey) return null;

	switch (identifierKey) {
		case 'ipdb': {
			const urlMatch = IPDB_RE.exec(input);
			if (urlMatch) return urlMatch[1];
			return BARE_DIGITS.test(input) ? input : null;
		}
		case 'opdb': {
			const urlMatch = OPDB_RE.exec(input);
			if (urlMatch) return urlMatch[1];
			return BARE_OPDB_ID.test(input) ? input : null;
		}
		default:
			return null;
	}
}

export function isDraftSubmittable(draft: CitationInstanceDraft): boolean {
	return draft.sourceId !== null && (draft.locator.length > 0 || draft.skipLocator);
}

export function emptyDraft(): CitationInstanceDraft {
	return { sourceId: null, sourceName: '', locator: '', skipLocator: false };
}

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

function parentContextFromSource(source: CitationSourceResult): ParentContext {
	return {
		id: source.id,
		name: source.name,
		source_type: source.source_type,
		author: source.author,
		child_input_mode: source.child_input_mode ?? null,
		// TODO: clean up cast once backend adds identifier_key to the schema
		identifier_key: ((source as Record<string, unknown>).identifier_key as string | null) ?? null
	};
}

/** Invalid action/state combos return current state unchanged. */
export function transition(state: CiteState, action: CiteAction): CiteState {
	switch (action.type) {
		case 'select_source': {
			if (state.stage !== 'search') return state;
			const draft = { ...state.draft, sourceId: action.source.id, sourceName: action.source.name };
			if (action.source.is_abstract) {
				return {
					stage: 'identify',
					draft: { ...draft, skipLocator: action.source.skip_locator },
					parent: parentContextFromSource(action.source)
				};
			}
			return {
				stage: 'locator',
				draft: { ...draft, skipLocator: action.source.skip_locator }
			};
		}

		case 'select_source_with_id': {
			if (state.stage !== 'search') return state;
			return {
				stage: 'identify',
				draft: {
					...state.draft,
					sourceId: action.source.id,
					sourceName: action.source.name
				},
				parent: parentContextFromSource(action.source),
				prefillIdentifier: action.identifier
			};
		}

		case 'select_child': {
			if (state.stage !== 'identify') return state;
			return {
				stage: 'locator',
				draft: {
					...state.draft,
					sourceId: action.sourceId,
					sourceName: action.sourceName,
					skipLocator: action.skipLocator
				}
			};
		}

		case 'start_create': {
			if (state.stage !== 'search' && state.stage !== 'identify') return state;
			return {
				stage: 'create',
				draft: state.draft,
				parent: state.stage === 'identify' ? state.parent : null,
				prefillName: action.prefillName
			};
		}

		case 'created': {
			if (state.stage !== 'create') return state;
			return {
				stage: 'locator',
				draft: {
					...state.draft,
					sourceId: action.sourceId,
					sourceName: action.sourceName,
					skipLocator: action.skipLocator
				}
			};
		}
	}
}
