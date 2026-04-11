/**
 * Shared mock data for citation autocomplete DOM tests.
 */

// ---------------------------------------------------------------------------
// Search results — returned by GET /api/citation-sources/search/
// ---------------------------------------------------------------------------

/** A plain book (non-abstract, no children). */
export const MOCK_SOURCES = [
	{
		id: 1,
		name: 'The Encyclopedia of Pinball',
		source_type: 'book',
		author: 'Richard Bueschel',
		publisher: 'Silverball Amusements',
		year: 1996,
		isbn: null,
		parent_id: null,
		has_children: false,
		is_abstract: false,
		skip_locator: false,
		child_input_mode: null,
		identifier_key: ''
	},
	{
		id: 2,
		name: 'Pinball Magazine',
		source_type: 'magazine',
		author: '',
		publisher: 'Pinball Mag',
		year: null,
		isbn: null,
		parent_id: null,
		has_children: false,
		is_abstract: false,
		skip_locator: false,
		child_input_mode: null,
		identifier_key: ''
	}
];

/** Abstract book parent with editions (search_children identify mode). */
export const ABSTRACT_BOOK_SOURCE = {
	id: 10,
	name: 'Pinball Machines: A History',
	source_type: 'book',
	author: 'Jane Author',
	publisher: 'Pinball Press',
	year: null,
	isbn: null,
	parent_id: null,
	has_children: true,
	is_abstract: true,
	skip_locator: false,
	child_input_mode: 'search_children',
	identifier_key: ''
};

/** Abstract IPDB parent (enter_identifier identify mode). */
export const IPDB_SOURCE = {
	id: 20,
	name: 'Internet Pinball Database',
	source_type: 'web',
	author: '',
	publisher: '',
	year: null,
	isbn: null,
	parent_id: null,
	has_children: true,
	is_abstract: true,
	skip_locator: false,
	child_input_mode: 'enter_identifier',
	identifier_key: 'ipdb'
};

// ---------------------------------------------------------------------------
// Children — returned by GET /api/citation-sources/{id}/ or .../children/
// ---------------------------------------------------------------------------

/** Book editions (children of ABSTRACT_BOOK_SOURCE). */
export const BOOK_CHILDREN = [
	{
		id: 11,
		name: 'Pinball Machines: A History — 2nd Edition',
		source_type: 'book',
		year: 2020,
		isbn: '978-1-234-56789-7',
		skip_locator: false,
		urls: []
	},
	{
		id: 12,
		name: 'Pinball Machines: A History — 1st Edition',
		source_type: 'book',
		year: 2010,
		isbn: '978-0-13-468599-1',
		skip_locator: false,
		urls: []
	}
];

/** IPDB child with skip_locator (web children skip locator). */
export const IPDB_CHILD = {
	id: 21,
	name: 'Internet Pinball Database #4836',
	source_type: 'web',
	year: null,
	isbn: null,
	skip_locator: true,
	urls: ['https://www.ipdb.org/machine.cgi?id=4836']
};

// ---------------------------------------------------------------------------
// Detail response — returned by GET /api/citation-sources/{id}/
// ---------------------------------------------------------------------------

export const BOOK_DETAIL_RESPONSE = {
	id: ABSTRACT_BOOK_SOURCE.id,
	name: ABSTRACT_BOOK_SOURCE.name,
	source_type: 'book',
	author: 'Jane Author',
	publisher: 'Pinball Press',
	year: null,
	month: null,
	day: null,
	date_note: '',
	isbn: null,
	description: '',
	identifier_key: '',
	skip_locator: false,
	parent: null,
	links: [],
	children: BOOK_CHILDREN,
	created_at: '2024-01-01T00:00:00Z',
	updated_at: '2024-01-01T00:00:00Z'
};

// ---------------------------------------------------------------------------
// Mutation responses
// ---------------------------------------------------------------------------

/** Minimal response from POST /api/citation-sources/ — component reads id, name, skip_locator. */
export const CREATED_SOURCE = { id: 3, name: 'New Source', skip_locator: false };

/** Response from POST /api/citation-sources/ when creating a new IPDB child. */
export const CREATED_IPDB_CHILD = {
	id: 22,
	name: 'Internet Pinball Database #9999',
	skip_locator: true
};

/** Minimal response from POST /api/citation-instances/ — component reads id. */
export const CREATED_INSTANCE = { id: 42 };
