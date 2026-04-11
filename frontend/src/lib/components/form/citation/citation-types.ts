import type { components } from '$lib/api/schema';
import type { createApiClient } from '$lib/api/client';

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
	/**
	 * Which URL/ID parsing convention applies to this source's children.
	 * Stopgap — will be subsumed by the extractor registry.
	 * See docs/plans/citations/CitationsDesign.md.
	 */
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
	/** Initial state. User searches for an existing source or pastes a URL. */
	| { stage: 'search'; draft: CitationInstanceDraft }
	/** User selected an abstract source (e.g. "IPDB") and must identify which child to cite. */
	| {
			stage: 'identify';
			draft: CitationInstanceDraft;
			parent: ParentContext;
			prefillIdentifier?: string;
	  }
	/** User is creating a new source manually. */
	| {
			stage: 'create';
			draft: CitationInstanceDraft;
			parent: ParentContext | null;
			prefillName: string;
	  }
	/** Source is chosen. User enters an optional locator (page number, URL fragment, etc.). */
	| { stage: 'locator'; draft: CitationInstanceDraft };

/** Inputs to the state machine, dispatched by stage components via the orchestrator. */
export type CiteAction =
	/** User picked a source from search results. Abstract → identify; concrete → locator. */
	| { type: 'source_selected'; source: CitationSourceResult; prefillIdentifier?: string }
	/** The exact citable CitationSource is known (via URL recognition, child selection, etc.). → locator. */
	| { type: 'source_identified'; sourceId: number; sourceName: string; skipLocator: boolean }
	/** User wants to create a new CitationSource. → create. */
	| { type: 'source_create_started'; prefillName: string }
	/** New CitationSource was created via API. → locator. */
	| { type: 'source_created'; sourceId: number; sourceName: string; skipLocator: boolean }
	/** User submitted or skipped the locator. */
	| { type: 'locator_submitted'; locator: string };

// ---------------------------------------------------------------------------
// Pure functions
// ---------------------------------------------------------------------------

export function suppressChildResults(results: CitationSourceResult[]): CitationSourceResult[] {
	const resultIds = new Set(results.map((r) => r.id));
	return results.filter((r) => !r.parent_id || !resultIds.has(r.parent_id));
}

// ---------------------------------------------------------------------------
// Identifier schemes — one entry per identifier_key value.
//
// Stopgap registry: will be subsumed by the server-side extractor layer.
// See docs/plans/citations/CitationsDesign.md.
// To add a new scheme, add one entry here — no other switch statements.
// ---------------------------------------------------------------------------

type IdentifierScheme = {
	/** Human-readable name shown when the URL is detected pre-selection. */
	sourceName: string;
	/** Regex that matches the full URL and captures the ID in group 1. */
	urlPattern: RegExp;
	/** Regex that matches a bare (non-URL) identifier. */
	barePattern: RegExp;
	/** Construct a canonical URL from a parsed ID. */
	buildUrl: (id: string) => string;
};

const IDENTIFIER_SCHEMES: Record<string, IdentifierScheme> = {
	ipdb: {
		sourceName: 'IPDB',
		urlPattern: /^https?:\/\/(?:www\.)?ipdb\.org\/machine\.cgi\?id=(\d+)/,
		barePattern: /^\d+$/,
		buildUrl: (id) => `https://www.ipdb.org/machine.cgi?id=${id}`
	},
	opdb: {
		sourceName: 'OPDB',
		urlPattern: /^https?:\/\/(?:www\.)?opdb\.org\/machines\/([A-Za-z0-9_-]+)/,
		barePattern: /^[A-Za-z0-9_-]+$/,
		buildUrl: (id) => `https://opdb.org/machines/${id}`
	}
};

/** Pre-selection: matches a pasted URL before any source is selected. */
export function detectSourceFromUrl(url: string): { sourceName: string; machineId: string } | null {
	for (const scheme of Object.values(IDENTIFIER_SCHEMES)) {
		const match = scheme.urlPattern.exec(url);
		if (match) return { sourceName: scheme.sourceName, machineId: match[1] };
	}
	return null;
}

/**
 * Post-selection: extracts a normalized identifier from user input.
 *
 * Instance-level rules (identifierKey: 'ipdb', 'opdb') take precedence.
 * Type-level rules (sourceType: 'book' → ISBN) are the fallback.
 */
export function parseIdentifierInput(
	sourceType: string,
	identifierKey: string | null,
	input: string
): string | null {
	if (!input) return null;

	// Instance-level: dispatch on identifier scheme
	if (identifierKey) {
		const scheme = IDENTIFIER_SCHEMES[identifierKey];
		if (!scheme) return null;
		const urlMatch = scheme.urlPattern.exec(input);
		if (urlMatch) return urlMatch[1];
		return scheme.barePattern.test(input) ? input : null;
	}

	// Type-level: derive from source type
	switch (sourceType) {
		case 'book':
			return parseIsbn(input);
		default:
			return null;
	}
}

/** Strip hyphens/spaces from input, validate check digit, return normalized ISBN or null. */
function parseIsbn(input: string): string | null {
	const stripped = input.replace(/[-\s]/g, '').toUpperCase();
	if (stripped.length === 13 && /^\d{13}$/.test(stripped)) {
		return isValidIsbn13(stripped) ? stripped : null;
	}
	if (stripped.length === 10 && /^\d{9}[\dX]$/.test(stripped)) {
		return isValidIsbn10(stripped) ? stripped : null;
	}
	return null;
}

function isValidIsbn13(isbn: string): boolean {
	let sum = 0;
	for (let i = 0; i < 13; i++) {
		sum += Number(isbn[i]) * (i % 2 === 0 ? 1 : 3);
	}
	return sum % 10 === 0;
}

function isValidIsbn10(isbn: string): boolean {
	let sum = 0;
	for (let i = 0; i < 10; i++) {
		const val = isbn[i] === 'X' ? 10 : Number(isbn[i]);
		sum += val * (10 - i);
	}
	return sum % 11 === 0;
}

/** Construct a canonical URL for a child source from its identifier key and parsed ID. */
export function buildChildUrl(identifierKey: string | null, parsedId: string): string | null {
	if (!identifierKey) return null;
	const scheme = IDENTIFIER_SCHEMES[identifierKey];
	return scheme ? scheme.buildUrl(parsedId) : null;
}

/** Find a child source whose URL matches the given identifier. */
export function findMatchingChild(
	children: ChildSource[],
	sourceType: string,
	identifierKey: string | null,
	targetId: string
): ChildSource | null {
	return (
		children.find((c) => {
			for (const url of c.urls) {
				const parsed = parseIdentifierInput(sourceType, identifierKey, url);
				if (parsed === targetId) return true;
			}
			return false;
		}) ?? null
	);
}

export type CreateChildResult =
	| { ok: true; data: { id: number; name: string; skip_locator: boolean } }
	| { ok: false; error: string };

/** Create a child citation source under a parent. */
export async function createChildSource(
	apiClient: ReturnType<typeof createApiClient>,
	parent: ParentContext,
	parsedId: string
): Promise<CreateChildResult> {
	const childUrl = buildChildUrl(parent.identifier_key, parsedId);
	const { data, error } = await apiClient.POST('/api/citation-sources/', {
		body: {
			name: `${parent.name} #${parsedId}`,
			source_type: parent.source_type,
			author: '',
			publisher: '',
			date_note: '',
			description: '',
			parent_id: parent.id,
			url: childUrl,
			link_label: '',
			link_type: 'homepage'
		}
	});
	if (error) {
		return { ok: false, error: typeof error === 'string' ? error : 'Failed to create source.' };
	}
	return { ok: true, data: { id: data.id, name: data.name, skip_locator: data.skip_locator } };
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

export function parentContextFromSource(source: CitationSourceResult): ParentContext {
	return {
		id: source.id,
		name: source.name,
		source_type: source.source_type,
		author: source.author,
		child_input_mode: source.child_input_mode ?? null,
		identifier_key: source.identifier_key || null
	};
}

/** Invalid action/state combos return current state unchanged. */
export function transition(state: CiteState, action: CiteAction): CiteState {
	switch (action.type) {
		case 'source_selected': {
			if (state.stage !== 'search') return state;
			const draft = { ...state.draft, sourceId: action.source.id, sourceName: action.source.name };
			if (action.source.is_abstract) {
				return {
					stage: 'identify',
					draft: { ...draft, skipLocator: action.source.skip_locator },
					parent: parentContextFromSource(action.source),
					prefillIdentifier: action.prefillIdentifier
				};
			}
			return {
				stage: 'locator',
				draft: { ...draft, skipLocator: action.source.skip_locator }
			};
		}

		case 'source_identified': {
			if (state.stage !== 'search' && state.stage !== 'identify') return state;
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

		case 'source_create_started': {
			if (state.stage !== 'search' && state.stage !== 'identify') return state;
			return {
				stage: 'create',
				draft: state.draft,
				parent: state.stage === 'identify' ? state.parent : null,
				prefillName: action.prefillName
			};
		}

		case 'source_created': {
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

		case 'locator_submitted': {
			if (state.stage !== 'locator') return state;
			return {
				...state,
				draft: { ...state.draft, locator: action.locator }
			};
		}
	}
}
