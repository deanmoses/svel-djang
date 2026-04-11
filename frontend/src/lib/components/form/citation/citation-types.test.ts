import { describe, it, expect } from 'vitest';
import {
	suppressChildResults,
	detectSourceFromUrl,
	parseIdentifierInput,
	buildChildUrl,
	findMatchingChild,
	isDraftSubmittable,
	emptyDraft,
	transition,
	type CitationSourceResult,
	type CiteState,
	type CitationInstanceDraft,
	type ChildSource,
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
		identifier_key: '',
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
	describe('instance-level: ipdb key', () => {
		it('parses IPDB URL', () => {
			expect(parseIdentifierInput('web', 'ipdb', 'https://www.ipdb.org/machine.cgi?id=4836')).toBe(
				'4836'
			);
		});

		it('parses bare digits', () => {
			expect(parseIdentifierInput('web', 'ipdb', '4836')).toBe('4836');
		});

		it('returns null for non-numeric non-URL input', () => {
			expect(parseIdentifierInput('web', 'ipdb', 'abc')).toBeNull();
		});

		it('returns null for empty input', () => {
			expect(parseIdentifierInput('web', 'ipdb', '')).toBeNull();
		});
	});

	describe('instance-level: opdb key', () => {
		it('parses OPDB URL', () => {
			expect(parseIdentifierInput('web', 'opdb', 'https://opdb.org/machines/abc-123')).toBe(
				'abc-123'
			);
		});

		it('parses bare alphanumeric ID', () => {
			expect(parseIdentifierInput('web', 'opdb', 'abc-123')).toBe('abc-123');
		});

		it('returns null for invalid characters', () => {
			expect(parseIdentifierInput('web', 'opdb', 'has spaces')).toBeNull();
		});

		it('returns null for empty input', () => {
			expect(parseIdentifierInput('web', 'opdb', '')).toBeNull();
		});
	});

	describe('type-level: book → ISBN', () => {
		it('parses ISBN-13 with hyphens', () => {
			expect(parseIdentifierInput('book', null, '978-0-13-468599-1')).toBe('9780134685991');
		});

		it('parses ISBN-13 bare digits', () => {
			expect(parseIdentifierInput('book', null, '9780134685991')).toBe('9780134685991');
		});

		it('parses ISBN-10 with hyphens', () => {
			expect(parseIdentifierInput('book', null, '0-13-468599-7')).toBe('0134685997');
		});

		it('parses ISBN-10 bare digits', () => {
			expect(parseIdentifierInput('book', null, '0134685997')).toBe('0134685997');
		});

		it('parses ISBN-10 with X check digit', () => {
			expect(parseIdentifierInput('book', null, '0-9752298-0-X')).toBe('097522980X');
		});

		it('rejects ISBN-13 with invalid check digit', () => {
			expect(parseIdentifierInput('book', null, '9780134685992')).toBeNull();
		});

		it('rejects ISBN-10 with invalid check digit', () => {
			expect(parseIdentifierInput('book', null, '0134685998')).toBeNull();
		});

		it('returns null for wrong digit count', () => {
			expect(parseIdentifierInput('book', null, '12345')).toBeNull();
		});

		it('returns null for non-ISBN text', () => {
			expect(parseIdentifierInput('book', null, 'some book title')).toBeNull();
		});

		it('returns null for empty input', () => {
			expect(parseIdentifierInput('book', null, '')).toBeNull();
		});
	});

	describe('instance-level takes precedence over type-level', () => {
		it('uses identifier_key when both source_type and key are present', () => {
			// A hypothetical book source that also has an instance-level key
			expect(parseIdentifierInput('book', 'ipdb', '4836')).toBe('4836');
		});
	});

	describe('unknown or null key with non-book type', () => {
		it('returns null for unknown key on web source', () => {
			expect(parseIdentifierInput('web', 'something', '12345')).toBeNull();
		});

		it('returns null for null key on web source', () => {
			expect(parseIdentifierInput('web', null, '12345')).toBeNull();
		});
	});
});

// ---------------------------------------------------------------------------
// buildChildUrl
// ---------------------------------------------------------------------------

describe('buildChildUrl', () => {
	it('builds IPDB URL from parsed ID', () => {
		expect(buildChildUrl('ipdb', '4836')).toBe('https://www.ipdb.org/machine.cgi?id=4836');
	});

	it('builds OPDB URL from parsed ID', () => {
		expect(buildChildUrl('opdb', 'abc-123')).toBe('https://opdb.org/machines/abc-123');
	});

	it('returns null for unknown key', () => {
		expect(buildChildUrl('something', '123')).toBeNull();
	});

	it('returns null for null key', () => {
		expect(buildChildUrl(null, '123')).toBeNull();
	});

	it('round-trips with parseIdentifierInput for IPDB', () => {
		const url = buildChildUrl('ipdb', '4836')!;
		expect(parseIdentifierInput('web', 'ipdb', url)).toBe('4836');
	});

	it('round-trips with parseIdentifierInput for OPDB', () => {
		const url = buildChildUrl('opdb', 'abc-123')!;
		expect(parseIdentifierInput('web', 'opdb', url)).toBe('abc-123');
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
	describe('source_selected', () => {
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
			const next = transition(state, { type: 'source_selected', source });

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
			const source = makeSource({
				id: 20,
				name: 'Internet Pinball Database',
				source_type: 'web',
				is_abstract: true,
				child_input_mode: 'enter_identifier',
				identifier_key: 'ipdb'
			});
			const state = searchState();
			const next = transition(state, { type: 'source_selected', source });

			expect(next.stage).toBe('identify');
			if (next.stage === 'identify') {
				expect(next.parent.identifier_key).toBe('ipdb');
			}
		});

		it('non-abstract source → locator stage with draft updated', () => {
			const source = makeSource({ id: 5, name: 'Concrete', skip_locator: false });
			const state = searchState();
			const next = transition(state, { type: 'source_selected', source });

			expect(next.stage).toBe('locator');
			expect(next.draft.sourceId).toBe(5);
			expect(next.draft.sourceName).toBe('Concrete');
			expect(next.draft.skipLocator).toBe(false);
		});

		it('non-abstract source with skip_locator → locator stage with skipLocator true', () => {
			const source = makeSource({ id: 6, name: 'Web Child', skip_locator: true });
			const state = searchState();
			const next = transition(state, { type: 'source_selected', source });

			expect(next.stage).toBe('locator');
			expect(next.draft.skipLocator).toBe(true);
		});
	});

	describe('source_identified', () => {
		it('from identify → locator stage with draft updated to child', () => {
			const state = identifyState(makeParent({ id: 10 }), { sourceId: 10, sourceName: 'Parent' });
			const next = transition(state, {
				type: 'source_identified',
				sourceId: 11,
				sourceName: 'Child Edition',
				skipLocator: false
			});

			expect(next.stage).toBe('locator');
			expect(next.draft.sourceId).toBe(11);
			expect(next.draft.sourceName).toBe('Child Edition');
			expect(next.draft.skipLocator).toBe(false);
		});

		it('from identify with skipLocator true → locator stage with skipLocator set', () => {
			const state = identifyState();
			const next = transition(state, {
				type: 'source_identified',
				sourceId: 12,
				sourceName: 'IPDB Machine 4836',
				skipLocator: true
			});

			expect(next.stage).toBe('locator');
			expect(next.draft.skipLocator).toBe(true);
		});

		it('from search → locator stage (URL recognition path)', () => {
			const state = searchState();
			const next = transition(state, {
				type: 'source_identified',
				sourceId: 21,
				sourceName: 'IPDB #4836',
				skipLocator: true
			});

			expect(next.stage).toBe('locator');
			expect(next.draft.sourceId).toBe(21);
			expect(next.draft.sourceName).toBe('IPDB #4836');
			expect(next.draft.skipLocator).toBe(true);
		});
	});

	describe('source_create_started', () => {
		it('from search → create with parent: null', () => {
			const state = searchState();
			const next = transition(state, { type: 'source_create_started', prefillName: 'New Source' });

			expect(next.stage).toBe('create');
			if (next.stage === 'create') {
				expect(next.parent).toBeNull();
				expect(next.prefillName).toBe('New Source');
			}
		});

		it('from identify → create with parent carried over', () => {
			const parent = makeParent({ id: 10, name: 'Book Series' });
			const state = identifyState(parent);
			const next = transition(state, { type: 'source_create_started', prefillName: 'New Edition' });

			expect(next.stage).toBe('create');
			if (next.stage === 'create') {
				expect(next.parent).toEqual(parent);
				expect(next.prefillName).toBe('New Edition');
			}
		});
	});

	describe('source_created', () => {
		it('→ locator stage with draft updated to new source', () => {
			const state: CiteState = {
				stage: 'create',
				draft: emptyDraft(),
				parent: null,
				prefillName: 'New Source'
			};
			const next = transition(state, {
				type: 'source_created',
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
				type: 'source_created',
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

		it('source_created from search → no-op', () => {
			const state = searchState();
			const next = transition(state, {
				type: 'source_created',
				sourceId: 1,
				sourceName: 'X',
				skipLocator: false
			});
			expect(next).toBe(state);
		});

		it('source_selected from identify → no-op', () => {
			const state = identifyState();
			const next = transition(state, { type: 'source_selected', source });
			expect(next).toBe(state);
		});

		it('source_create_started from locator → no-op', () => {
			const state: CiteState = { stage: 'locator', draft: emptyDraft() };
			const next = transition(state, { type: 'source_create_started', prefillName: 'X' });
			expect(next).toBe(state);
		});

		it('source_create_started from create → no-op', () => {
			const state: CiteState = {
				stage: 'create',
				draft: emptyDraft(),
				parent: null,
				prefillName: 'Y'
			};
			const next = transition(state, { type: 'source_create_started', prefillName: 'X' });
			expect(next).toBe(state);
		});
	});

	describe('source_selected with prefillIdentifier', () => {
		it('abstract source with prefillIdentifier → identify stage carries it through', () => {
			const source = makeSource({
				id: 10,
				name: 'IPDB',
				is_abstract: true,
				child_input_mode: 'enter_identifier',
				identifier_key: 'ipdb'
			});
			const state = searchState();
			const next = transition(state, {
				type: 'source_selected',
				source,
				prefillIdentifier: '4836'
			});

			expect(next.stage).toBe('identify');
			if (next.stage === 'identify') {
				expect(next.prefillIdentifier).toBe('4836');
			}
		});

		it('abstract source without prefillIdentifier → identify stage with undefined', () => {
			const source = makeSource({
				id: 10,
				name: 'IPDB',
				is_abstract: true,
				child_input_mode: 'enter_identifier'
			});
			const state = searchState();
			const next = transition(state, { type: 'source_selected', source });

			expect(next.stage).toBe('identify');
			if (next.stage === 'identify') {
				expect(next.prefillIdentifier).toBeUndefined();
			}
		});
	});

	describe('locator_submitted', () => {
		it('from locator → same stage with draft.locator updated', () => {
			const state: CiteState = {
				stage: 'locator',
				draft: { sourceId: 5, sourceName: 'X', locator: '', skipLocator: false }
			};
			const next = transition(state, { type: 'locator_submitted', locator: 'p. 42' });

			expect(next.stage).toBe('locator');
			expect(next.draft.locator).toBe('p. 42');
			expect(next.draft.sourceId).toBe(5);
		});

		it('from locator with empty locator → works (skip path)', () => {
			const state: CiteState = {
				stage: 'locator',
				draft: { sourceId: 5, sourceName: 'X', locator: '', skipLocator: false }
			};
			const next = transition(state, { type: 'locator_submitted', locator: '' });

			expect(next.stage).toBe('locator');
			expect(next.draft.locator).toBe('');
		});

		it('from search → no-op', () => {
			const state = searchState();
			const next = transition(state, { type: 'locator_submitted', locator: 'p. 1' });
			expect(next).toBe(state);
		});

		it('from identify → no-op', () => {
			const state = identifyState();
			const next = transition(state, { type: 'locator_submitted', locator: 'p. 1' });
			expect(next).toBe(state);
		});
	});
});

// ---------------------------------------------------------------------------
// findMatchingChild
// ---------------------------------------------------------------------------

describe('findMatchingChild', () => {
	function makeChild(overrides: Partial<ChildSource> = {}): ChildSource {
		return {
			id: 1,
			name: 'Child',
			source_type: 'web',
			skip_locator: true,
			urls: [],
			...overrides
		};
	}

	it('returns matching child when a URL parses to the target ID', () => {
		const child = makeChild({
			id: 11,
			name: 'IPDB #4836',
			urls: ['https://www.ipdb.org/machine.cgi?id=4836']
		});
		const result = findMatchingChild([child], 'web', 'ipdb', '4836');
		expect(result).toBe(child);
	});

	it('returns null when no children match', () => {
		const child = makeChild({
			urls: ['https://www.ipdb.org/machine.cgi?id=9999']
		});
		const result = findMatchingChild([child], 'web', 'ipdb', '4836');
		expect(result).toBeNull();
	});

	it('returns null on empty array', () => {
		expect(findMatchingChild([], 'web', 'ipdb', '4836')).toBeNull();
	});

	it('returns first match when multiple children match', () => {
		const first = makeChild({
			id: 11,
			urls: ['https://www.ipdb.org/machine.cgi?id=4836']
		});
		const second = makeChild({
			id: 12,
			urls: ['https://www.ipdb.org/machine.cgi?id=4836']
		});
		expect(findMatchingChild([first, second], 'web', 'ipdb', '4836')).toBe(first);
	});

	it('matches against multiple URLs on a single child', () => {
		const child = makeChild({
			urls: ['https://example.com', 'https://www.ipdb.org/machine.cgi?id=4836']
		});
		expect(findMatchingChild([child], 'web', 'ipdb', '4836')).toBe(child);
	});
});
