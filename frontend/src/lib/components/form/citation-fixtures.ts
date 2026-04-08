/**
 * Shared mock data for citation autocomplete DOM tests.
 */

export const MOCK_SOURCES = [
	{
		id: 1,
		name: 'The Encyclopedia of Pinball',
		source_type: 'book',
		author: 'Richard Bueschel',
		publisher: 'Silverball Amusements',
		year: 1996,
		isbn: null
	},
	{
		id: 2,
		name: 'Pinball Magazine',
		source_type: 'magazine',
		author: '',
		publisher: 'Pinball Mag',
		year: null,
		isbn: null
	}
];

/** Minimal response from POST /api/citation-sources/ — component reads id and name. */
export const CREATED_SOURCE = { id: 3, name: 'New Source' };

/** Minimal response from POST /api/citation-instances/ — component reads id. */
export const CREATED_INSTANCE = { id: 42 };
