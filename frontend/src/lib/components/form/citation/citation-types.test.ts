import { describe, it, expect } from 'vitest';
import {
	suppressChildResults,
	detectSourceFromUrl,
	parseIdentifierInput,
	isDraftSubmittable,
	emptyDraft,
	transition,
	type CitationSourceResult,
	type CiteState,
	type CitationInstanceDraft,
	type ParentContext
} from './citation-types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeSource(overrides: Partial<CitationSourceResult> = {}): CitationSourceResult {
	return {
		id: 1,
		name: 'Test Source',
		source_type: 'book',
		author: '',
		publisher: '',
		parent_id: null,
		has_children: false,
		is_abstract: false,
		skip_locator: false,
		child_input_mode: null,
		...overrides
	};
}

function makeParent(overrides: Partial<ParentContext> = {}): ParentContext {
	return {
		id: 1,
		name: 'Parent',
		source_type: 'book',
		author: '',
		child_input_mode: 'search_children',
		identifier_key: null,
		...overrides
	};
}

function searchState(draftOverrides: Partial<CitationInstanceDraft> = {}): CiteState {
	return { stage: 'search', draft: { ...emptyDraft(), ...draftOverrides } };
}

function identifyState(
	parent: ParentContext = makeParent(),
	draftOverrides: Partial<CitationInstanceDraft> = {}
): CiteState {
	return { stage: 'identify', draft: { ...emptyDraft(), ...draftOverrides }, parent };
}

// ---------------------------------------------------------------------------
// suppressChildResults
// ---------------------------------------------------------------------------

describe('suppressChildResults', () => {
	it('filters out children whose parent is in the result set', () => {
		const parent = makeSource({ id: 10, has_children: true });
		const child = makeSource({ id: 11, parent_id: 10 });
		const result = suppressChildResults([parent, child]);
		expect(result).toEqual([parent]);
	});

	it('keeps children whose parent is NOT in the result set', () => {
		const child = makeSource({ id: 11, parent_id: 99 });
		const result = suppressChildResults([child]);
		expect(result).toEqual([child]);
	});

	it('returns all items when there are no parents', () => {
		const a = makeSource({ id: 1 });
		const b = makeSource({ id: 2 });
		const result = suppressChildResults([a, b]);
		expect(result).toEqual([a, b]);
	});

	it('returns empty array for empty input', () => {
		expect(suppressChildResults([])).toEqual([]);
	});
});

// ---------------------------------------------------------------------------
// detectSourceFromUrl
// ---------------------------------------------------------------------------

describe('detectSourceFromUrl', () => {
	it('detects IPDB URL', () => {
		expect(detectSourceFromUrl('https://www.ipdb.org/machine.cgi?id=4836')).toEqual({
			sourceName: 'IPDB',
			machineId: '4836'
		});
	});

	it('detects IPDB URL without www', () => {
		expect(detectSourceFromUrl('https://ipdb.org/machine.cgi?id=123')).toEqual({
			sourceName: 'IPDB',
			machineId: '123'
		});
	});

	it('detects IPDB URL with http', () => {
		expect(detectSourceFromUrl('http://ipdb.org/machine.cgi?id=999')).toEqual({
			sourceName: 'IPDB',
			machineId: '999'
		});
	});

	it('detects OPDB URL', () => {
		expect(detectSourceFromUrl('https://opdb.org/machines/abc-123')).toEqual({
			sourceName: 'OPDB',
			machineId: 'abc-123'
		});
	});

	it('detects OPDB URL without www', () => {
		expect(detectSourceFromUrl('https://opdb.org/machines/foo_bar')).toEqual({
			sourceName: 'OPDB',
			machineId: 'foo_bar'
		});
	});

	it('detects OPDB URL with www and http', () => {
		expect(detectSourceFromUrl('http://www.opdb.org/machines/Xyz99')).toEqual({
			sourceName: 'OPDB',
			machineId: 'Xyz99'
		});
	});

	it('returns null for non-matching URLs', () => {
		expect(detectSourceFromUrl('https://example.com/page')).toBeNull();
	});

	it('returns null for empty string', () => {
		expect(detectSourceFromUrl('')).toBeNull();
	});
});

// ---------------------------------------------------------------------------
// parseIdentifierInput
// ---------------------------------------------------------------------------

describe('parseIdentifierInput', () => {
	describe('ipdb key', () => {
		it('parses IPDB URL', () => {
			expect(parseIdentifierInput('ipdb', 'https://www.ipdb.org/machine.cgi?id=4836')).toBe('4836');
		});

		it('parses bare digits', () => {
			expect(parseIdentifierInput('ipdb', '4836')).toBe('4836');
		});

		it('returns null for non-numeric non-URL input', () => {
			expect(parseIdentifierInput('ipdb', 'abc')).toBeNull();
		});

		it('returns null for empty input', () => {
			expect(parseIdentifierInput('ipdb', '')).toBeNull();
		});
	});

	describe('opdb key', () => {
		it('parses OPDB URL', () => {
			expect(parseIdentifierInput('opdb', 'https://opdb.org/machines/abc-123')).toBe('abc-123');
		});

		it('parses bare alphanumeric ID', () => {
			expect(parseIdentifierInput('opdb', 'abc-123')).toBe('abc-123');
		});

		it('returns null for invalid characters', () => {
			expect(parseIdentifierInput('opdb', 'has spaces')).toBeNull();
		});

		it('returns null for empty input', () => {
			expect(parseIdentifierInput('opdb', '')).toBeNull();
		});
	});

	describe('unknown or null key', () => {
		it('returns null for unknown key', () => {
			expect(parseIdentifierInput('something', '12345')).toBeNull();
		});

		it('returns null for null key', () => {
			expect(parseIdentifierInput(null, '12345')).toBeNull();
		});
	});
});

// ---------------------------------------------------------------------------
// isDraftSubmittable
// ---------------------------------------------------------------------------

describe('isDraftSubmittable', () => {
	it('returns true when sourceId is set and locator is non-empty', () => {
		expect(
			isDraftSubmittable({ sourceId: 1, sourceName: 'X', locator: 'p.5', skipLocator: false })
		).toBe(true);
	});

	it('returns true when sourceId is set and skipLocator is true', () => {
		expect(
			isDraftSubmittable({ sourceId: 1, sourceName: 'X', locator: '', skipLocator: true })
		).toBe(true);
	});

	it('returns false when sourceId is null', () => {
		expect(
			isDraftSubmittable({ sourceId: null, sourceName: '', locator: 'p.5', skipLocator: false })
		).toBe(false);
	});

	it('returns false when sourceId is set but locator empty and skipLocator false', () => {
		expect(
			isDraftSubmittable({ sourceId: 1, sourceName: 'X', locator: '', skipLocator: false })
		).toBe(false);
	});

	it('returns true when both locator and skipLocator are set', () => {
		expect(
			isDraftSubmittable({ sourceId: 1, sourceName: 'X', locator: 'p.5', skipLocator: true })
		).toBe(true);
	});
});

// ---------------------------------------------------------------------------
// emptyDraft
// ---------------------------------------------------------------------------

describe('emptyDraft', () => {
	it('returns a fresh empty draft', () => {
		expect(emptyDraft()).toEqual({
			sourceId: null,
			sourceName: '',
			locator: '',
			skipLocator: false
		});
	});

	it('returns a new object each time', () => {
		expect(emptyDraft()).not.toBe(emptyDraft());
	});
});

// ---------------------------------------------------------------------------
// transition (state machine)
// ---------------------------------------------------------------------------

describe('transition', () => {
	describe('select_source', () => {
		it('abstract source → identify stage with parentContext', () => {
			const source = makeSource({
				id: 10,
				name: 'Book Series',
				source_type: 'book',
				author: 'Author A',
				is_abstract: true,
				child_input_mode: 'search_children'
			});
			const state = searchState();
			const next = transition(state, { type: 'select_source', source });

			expect(next.stage).toBe('identify');
			if (next.stage === 'identify') {
				expect(next.parent).toEqual({
					id: 10,
					name: 'Book Series',
					source_type: 'book',
					author: 'Author A',
					child_input_mode: 'search_children',
					identifier_key: null
				});
				expect(next.draft.sourceId).toBe(10);
				expect(next.draft.sourceName).toBe('Book Series');
				expect(next.prefillIdentifier).toBeUndefined();
			}
		});

		it('abstract web source carries identifier_key through to parentContext', () => {
			// identifier_key is not yet in the generated schema; simulate it arriving from the API
			const source = {
				...makeSource({
					id: 20,
					name: 'Internet Pinball Database',
					source_type: 'web',
					is_abstract: true,
					child_input_mode: 'enter_identifier'
				}),
				identifier_key: 'ipdb'
			} as CitationSourceResult;
			const state = searchState();
			const next = transition(state, { type: 'select_source', source });

			expect(next.stage).toBe('identify');
			if (next.stage === 'identify') {
				expect(next.parent.identifier_key).toBe('ipdb');
			}
		});

		it('non-abstract source → locator stage with draft updated', () => {
			const source = makeSource({ id: 5, name: 'Concrete', skip_locator: false });
			const state = searchState();
			const next = transition(state, { type: 'select_source', source });

			expect(next.stage).toBe('locator');
			expect(next.draft.sourceId).toBe(5);
			expect(next.draft.sourceName).toBe('Concrete');
			expect(next.draft.skipLocator).toBe(false);
		});

		it('non-abstract source with skip_locator → locator stage with skipLocator true', () => {
			const source = makeSource({ id: 6, name: 'Web Child', skip_locator: true });
			const state = searchState();
			const next = transition(state, { type: 'select_source', source });

			expect(next.stage).toBe('locator');
			expect(next.draft.skipLocator).toBe(true);
		});
	});

	describe('select_source_with_id', () => {
		it('→ identify stage with prefillIdentifier set', () => {
			const source = makeSource({
				id: 20,
				name: 'IPDB',
				source_type: 'web',
				is_abstract: true,
				child_input_mode: 'enter_identifier'
			});
			const state = searchState();
			const next = transition(state, {
				type: 'select_source_with_id',
				source,
				identifier: '4836'
			});

			expect(next.stage).toBe('identify');
			if (next.stage === 'identify') {
				expect(next.prefillIdentifier).toBe('4836');
				expect(next.parent.id).toBe(20);
				expect(next.draft.sourceId).toBe(20);
				expect(next.draft.sourceName).toBe('IPDB');
			}
		});
	});

	describe('select_child', () => {
		it('→ locator stage with draft updated to child', () => {
			const state = identifyState(makeParent({ id: 10 }), { sourceId: 10, sourceName: 'Parent' });
			const next = transition(state, {
				type: 'select_child',
				sourceId: 11,
				sourceName: 'Child Edition',
				skipLocator: false
			});

			expect(next.stage).toBe('locator');
			expect(next.draft.sourceId).toBe(11);
			expect(next.draft.sourceName).toBe('Child Edition');
			expect(next.draft.skipLocator).toBe(false);
		});

		it('with skipLocator true → locator stage with skipLocator set', () => {
			const state = identifyState();
			const next = transition(state, {
				type: 'select_child',
				sourceId: 12,
				sourceName: 'IPDB Machine 4836',
				skipLocator: true
			});

			expect(next.stage).toBe('locator');
			expect(next.draft.skipLocator).toBe(true);
		});
	});

	describe('start_create', () => {
		it('from search → create with parent: null', () => {
			const state = searchState();
			const next = transition(state, { type: 'start_create', prefillName: 'New Source' });

			expect(next.stage).toBe('create');
			if (next.stage === 'create') {
				expect(next.parent).toBeNull();
				expect(next.prefillName).toBe('New Source');
			}
		});

		it('from identify → create with parent carried over', () => {
			const parent = makeParent({ id: 10, name: 'Book Series' });
			const state = identifyState(parent);
			const next = transition(state, { type: 'start_create', prefillName: 'New Edition' });

			expect(next.stage).toBe('create');
			if (next.stage === 'create') {
				expect(next.parent).toEqual(parent);
				expect(next.prefillName).toBe('New Edition');
			}
		});
	});

	describe('created', () => {
		it('→ locator stage with draft updated to new source', () => {
			const state: CiteState = {
				stage: 'create',
				draft: emptyDraft(),
				parent: null,
				prefillName: 'New Source'
			};
			const next = transition(state, {
				type: 'created',
				sourceId: 50,
				sourceName: 'New Source',
				skipLocator: false
			});

			expect(next.stage).toBe('locator');
			expect(next.draft.sourceId).toBe(50);
			expect(next.draft.sourceName).toBe('New Source');
			expect(next.draft.skipLocator).toBe(false);
		});

		it('with skipLocator → locator stage with skipLocator true', () => {
			const state: CiteState = {
				stage: 'create',
				draft: emptyDraft(),
				parent: makeParent(),
				prefillName: 'Web Child'
			};
			const next = transition(state, {
				type: 'created',
				sourceId: 51,
				sourceName: 'Web Child',
				skipLocator: true
			});

			expect(next.stage).toBe('locator');
			expect(next.draft.skipLocator).toBe(true);
		});
	});

	describe('invalid transitions', () => {
		const source = makeSource({ id: 1 });

		it('select_child from search → no-op', () => {
			const state = searchState();
			const next = transition(state, {
				type: 'select_child',
				sourceId: 1,
				sourceName: 'X',
				skipLocator: false
			});
			expect(next).toBe(state);
		});

		it('created from search → no-op', () => {
			const state = searchState();
			const next = transition(state, {
				type: 'created',
				sourceId: 1,
				sourceName: 'X',
				skipLocator: false
			});
			expect(next).toBe(state);
		});

		it('select_source from identify → no-op', () => {
			const state = identifyState();
			const next = transition(state, { type: 'select_source', source });
			expect(next).toBe(state);
		});

		it('select_source_with_id from identify → no-op', () => {
			const state = identifyState();
			const next = transition(state, { type: 'select_source_with_id', source, identifier: '1' });
			expect(next).toBe(state);
		});

		it('start_create from locator → no-op', () => {
			const state: CiteState = { stage: 'locator', draft: emptyDraft() };
			const next = transition(state, { type: 'start_create', prefillName: 'X' });
			expect(next).toBe(state);
		});

		it('start_create from create → no-op', () => {
			const state: CiteState = {
				stage: 'create',
				draft: emptyDraft(),
				parent: null,
				prefillName: 'Y'
			};
			const next = transition(state, { type: 'start_create', prefillName: 'X' });
			expect(next).toBe(state);
		});
	});
});
