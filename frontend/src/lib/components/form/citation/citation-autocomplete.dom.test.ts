import { render, screen, fireEvent } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CitationAutocomplete from './CitationAutocomplete.svelte';
import {
	MOCK_SOURCES,
	CREATED_INSTANCE,
	CREATED_IPDB_CHILD,
	ABSTRACT_BOOK_SOURCE,
	IPDB_SOURCE,
	IPDB_CHILD,
	BOOK_CHILDREN,
	BOOK_DETAIL_RESPONSE,
	CREATED_SOURCE
} from './citation-fixtures';

const { mockGET, mockPOST } = vi.hoisted(() => ({
	mockGET: vi.fn(),
	mockPOST: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: { GET: mockGET, POST: mockPOST }
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderAutocomplete() {
	const oncomplete = vi.fn();
	const oncancel = vi.fn();
	const onback = vi.fn();

	render(CitationAutocomplete, { oncomplete, oncancel, onback });

	return { oncomplete, oncancel, onback };
}

function getSearchInput() {
	return screen.getByRole('combobox', { name: /search sources/i }) as HTMLInputElement;
}

async function searchAndWaitFor(
	user: ReturnType<typeof userEvent.setup>,
	query: string,
	source: { name: string }
) {
	const input = getSearchInput();
	input.focus();
	await user.keyboard(query);

	await vi.waitFor(() => {
		expect(screen.getByRole('option', { name: new RegExp(source.name) })).toBeInTheDocument();
	});

	return input;
}

async function selectSource(source: { name: string }) {
	fireEvent.pointerDown(screen.getByRole('option', { name: new RegExp(source.name) }));
}

/**
 * Navigate from search to the book identify-by-search stage:
 * search → select abstract book → children load.
 */
async function enterBookIdentifyStage(user: ReturnType<typeof userEvent.setup>) {
	mockGET.mockImplementation((url: string) => {
		if (url === '/api/citation-sources/search/')
			return Promise.resolve({ data: [ABSTRACT_BOOK_SOURCE] });
		if (url === '/api/citation-sources/{source_id}/')
			return Promise.resolve({ data: BOOK_DETAIL_RESPONSE });
		return Promise.resolve({ data: [] });
	});

	await searchAndWaitFor(user, 'pinball', ABSTRACT_BOOK_SOURCE);
	await selectSource(ABSTRACT_BOOK_SOURCE);

	await vi.waitFor(() => {
		expect(
			screen.getByRole('option', { name: new RegExp(BOOK_CHILDREN[0].name) })
		).toBeInTheDocument();
	});
}

/**
 * Navigate from search to the IPDB identify-by-input stage and type an ID.
 */
async function enterIpdbIdentifyStage(
	user: ReturnType<typeof userEvent.setup>,
	childrenResponse: (typeof IPDB_CHILD)[],
	identifier: string
) {
	mockGET.mockImplementation((url: string) => {
		if (url === '/api/citation-sources/search/') return Promise.resolve({ data: [IPDB_SOURCE] });
		if (url === '/api/citation-sources/{source_id}/children/')
			return Promise.resolve({ data: childrenResponse });
		return Promise.resolve({ data: [] });
	});

	await searchAndWaitFor(user, 'IPDB', IPDB_SOURCE);
	await selectSource(IPDB_SOURCE);

	await vi.waitFor(() => {
		expect(screen.getByRole('textbox', { name: /enter identifier/i })).toBeInTheDocument();
	});

	const idInput = screen.getByRole('textbox', { name: /enter identifier/i });
	idInput.focus();
	await user.keyboard(identifier);
}

/**
 * Navigate from search to the create stage via "Create new".
 */
async function enterCreateStage(user: ReturnType<typeof userEvent.setup>, query = 'New Book') {
	await searchAndWaitFor(user, query, MOCK_SOURCES[0]);
	fireEvent.pointerDown(screen.getByRole('option', { name: new RegExp(`Create "${query}"`) }));

	await vi.waitFor(() => {
		expect(screen.getByText('New source')).toBeInTheDocument();
	});
}

/**
 * Navigate from search to the locator stage by selecting a non-abstract source.
 */
async function enterLocatorStage(user: ReturnType<typeof userEvent.setup>) {
	await searchAndWaitFor(user, 'pinball', MOCK_SOURCES[0]);
	await selectSource(MOCK_SOURCES[0]);

	await vi.waitFor(() => {
		expect(screen.getByRole('textbox', { name: /citation locator/i })).toBeInTheDocument();
	});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CitationAutocomplete (component-level)', () => {
	beforeEach(() => {
		mockGET.mockReset().mockResolvedValue({ data: MOCK_SOURCES });
		mockPOST.mockReset();
	});

	// -----------------------------------------------------------------------
	// Error and retry paths
	// -----------------------------------------------------------------------

	describe('error and retry paths', () => {
		it('shows validation error when submitting create stage with empty name', async () => {
			const user = userEvent.setup();
			renderAutocomplete();

			await enterCreateStage(user);

			// Clear the pre-filled name
			const nameInput = screen.getByPlaceholderText('Name') as HTMLInputElement;
			nameInput.focus();
			await user.clear(nameInput);

			// Submit the form — type="submit" button requires click, not pointerDown
			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			await vi.waitFor(() => {
				expect(screen.getByText('Name is required.')).toBeInTheDocument();
			});
		});

		it('shows error on create stage POST failure and allows retry', async () => {
			const user = userEvent.setup();
			renderAutocomplete();

			await enterCreateStage(user, 'Test Source');

			// First attempt: POST fails (non-string error triggers generic message)
			mockPOST.mockResolvedValueOnce({ error: { detail: 'Server error' } });
			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			await vi.waitFor(() => {
				expect(screen.getByText('Failed to create source.')).toBeInTheDocument();
			});

			// Retry: POST succeeds
			mockPOST
				.mockResolvedValueOnce({ data: CREATED_SOURCE })
				.mockResolvedValueOnce({ data: CREATED_INSTANCE });
			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			// Error clears and flow continues (to locator, since CREATED_SOURCE has skip_locator: false)
			await vi.waitFor(() => {
				expect(screen.queryByText('Failed to create source.')).not.toBeInTheDocument();
				expect(screen.getByRole('textbox', { name: /citation locator/i })).toBeInTheDocument();
			});
		});

		it('shows error when citation instance POST fails at locator stage', async () => {
			const user = userEvent.setup();
			renderAutocomplete();

			await enterLocatorStage(user);

			// POST fails
			mockPOST.mockResolvedValueOnce({ error: 'Server error' });
			fireEvent.pointerDown(screen.getByRole('button', { name: 'Insert' }));

			await vi.waitFor(() => {
				expect(screen.getByText('Failed to create citation.')).toBeInTheDocument();
			});
		});

		it('shows lookup failure in ByInput stage', async () => {
			const user = userEvent.setup();
			renderAutocomplete();

			mockGET.mockImplementation((url: string) => {
				if (url === '/api/citation-sources/search/')
					return Promise.resolve({ data: [IPDB_SOURCE] });
				if (url === '/api/citation-sources/{source_id}/children/')
					return Promise.reject(new Error('Network error'));
				return Promise.resolve({ data: [] });
			});

			await searchAndWaitFor(user, 'IPDB', IPDB_SOURCE);
			await selectSource(IPDB_SOURCE);

			await vi.waitFor(() => {
				expect(screen.getByRole('textbox', { name: /enter identifier/i })).toBeInTheDocument();
			});

			const idInput = screen.getByRole('textbox', { name: /enter identifier/i });
			idInput.focus();
			await user.keyboard('4836');

			await vi.waitFor(() => {
				expect(screen.getByText(/lookup failed/i)).toBeInTheDocument();
			});
		});

		it('shows error when ByInput create POST fails', async () => {
			const user = userEvent.setup();
			renderAutocomplete();

			await enterIpdbIdentifyStage(user, [], '9999');

			await vi.waitFor(() => {
				expect(screen.getByRole('button', { name: 'Create & cite' })).toBeInTheDocument();
			});

			// Non-string error triggers the generic "Failed to create source." message
			mockPOST.mockResolvedValueOnce({ error: { detail: 'Server error' } });
			fireEvent.pointerDown(screen.getByRole('button', { name: 'Create & cite' }));

			await vi.waitFor(() => {
				expect(screen.getByText('Failed to create source.')).toBeInTheDocument();
			});
		});
	});

	// -----------------------------------------------------------------------
	// Back / cancel behavior
	// -----------------------------------------------------------------------

	describe('back and cancel behavior', () => {
		it('fires onback when backing out of search stage', () => {
			const { onback } = renderAutocomplete();
			const input = getSearchInput();

			input.focus();
			fireEvent.keyDown(input, { key: 'Backspace' });

			expect(onback).toHaveBeenCalledOnce();
		});

		it('returns to search when backing out of identify stage', async () => {
			const user = userEvent.setup();
			const { onback } = renderAutocomplete();

			await enterBookIdentifyStage(user);

			// Back from identify → should return to search, not fire onback
			const filterInput = screen.getByRole('combobox', { name: /filter editions/i });
			filterInput.focus();
			fireEvent.keyDown(filterInput, { key: 'Backspace' });

			await vi.waitFor(() => {
				expect(getSearchInput()).toBeInTheDocument();
			});
			expect(onback).not.toHaveBeenCalled();
		});

		it('returns to search when backing out of create stage', async () => {
			const user = userEvent.setup();
			const { onback } = renderAutocomplete();

			await enterCreateStage(user);

			// DropdownHeader back button
			fireEvent.pointerDown(screen.getByRole('button', { name: /back/i }));

			await vi.waitFor(() => {
				expect(getSearchInput()).toBeInTheDocument();
			});
			expect(onback).not.toHaveBeenCalled();
		});

		it('returns to search when backing out of locator stage', async () => {
			const user = userEvent.setup();
			const { onback } = renderAutocomplete();

			await enterLocatorStage(user);

			const locatorInput = screen.getByRole('textbox', { name: /citation locator/i });
			locatorInput.focus();
			fireEvent.keyDown(locatorInput, { key: 'Backspace' });

			await vi.waitFor(() => {
				expect(getSearchInput()).toBeInTheDocument();
			});
			expect(onback).not.toHaveBeenCalled();
		});

		it('fires oncancel on Escape from search stage', () => {
			const { oncancel } = renderAutocomplete();
			const input = getSearchInput();

			input.focus();
			fireEvent.keyDown(input, { key: 'Escape' });

			expect(oncancel).toHaveBeenCalledOnce();
		});

		it('fires oncancel on Escape from identify stage', async () => {
			const user = userEvent.setup();
			const { oncancel } = renderAutocomplete();

			await enterBookIdentifyStage(user);

			const filterInput = screen.getByRole('combobox', { name: /filter editions/i });
			filterInput.focus();
			fireEvent.keyDown(filterInput, { key: 'Escape' });

			expect(oncancel).toHaveBeenCalledOnce();
		});

		it('fires oncancel on Escape from create stage', async () => {
			const user = userEvent.setup();
			const { oncancel } = renderAutocomplete();

			await enterCreateStage(user);

			const nameInput = screen.getByPlaceholderText('Name');
			fireEvent.keyDown(nameInput, { key: 'Escape' });

			expect(oncancel).toHaveBeenCalledOnce();
		});

		it('fires oncancel on Escape from locator stage', async () => {
			const user = userEvent.setup();
			const { oncancel } = renderAutocomplete();

			await enterLocatorStage(user);

			const locatorInput = screen.getByRole('textbox', { name: /citation locator/i });
			locatorInput.focus();
			fireEvent.keyDown(locatorInput, { key: 'Escape' });

			expect(oncancel).toHaveBeenCalledOnce();
		});
	});

	// -----------------------------------------------------------------------
	// Orchestrator guards
	// -----------------------------------------------------------------------

	describe('orchestrator guards', () => {
		it('prevents duplicate citation submission on rapid double-click', async () => {
			const user = userEvent.setup();
			renderAutocomplete();

			await enterLocatorStage(user);

			// Mock a POST that resolves slowly
			let resolvePost!: (value: { data: typeof CREATED_INSTANCE }) => void;
			const slowPost = new Promise<{ data: typeof CREATED_INSTANCE }>((resolve) => {
				resolvePost = resolve;
			});
			mockPOST.mockReturnValue(slowPost);

			const insertBtn = screen.getByRole('button', { name: 'Insert' });
			fireEvent.pointerDown(insertBtn);
			fireEvent.pointerDown(insertBtn);

			resolvePost({ data: CREATED_INSTANCE });

			await vi.waitFor(() => {
				expect(mockPOST).toHaveBeenCalledTimes(1);
			});
		});
	});

	// -----------------------------------------------------------------------
	// IPDB flows (migrated from integration tests)
	// -----------------------------------------------------------------------

	describe('IPDB identify-by-input flow', () => {
		it('cites an existing IPDB child, skipping locator', async () => {
			const user = userEvent.setup();
			const { oncomplete } = renderAutocomplete();

			await enterIpdbIdentifyStage(user, [IPDB_CHILD], '4836');

			await vi.waitFor(() => {
				expect(screen.getByText(IPDB_CHILD.name)).toBeInTheDocument();
				expect(screen.getByRole('button', { name: 'Cite' })).toBeInTheDocument();
			});

			mockPOST.mockResolvedValueOnce({ data: CREATED_INSTANCE });
			fireEvent.pointerDown(screen.getByRole('button', { name: 'Cite' }));

			await vi.waitFor(() => {
				expect(oncomplete).toHaveBeenCalledWith(`[[cite:${CREATED_INSTANCE.id}]]`);
			});

			expect(mockPOST).toHaveBeenCalledWith('/api/citation-instances/', {
				body: { citation_source_id: IPDB_CHILD.id, locator: '' }
			});
		});

		it('creates a new IPDB child and cites it when no match exists', async () => {
			const user = userEvent.setup();
			const { oncomplete } = renderAutocomplete();

			await enterIpdbIdentifyStage(user, [], '9999');

			await vi.waitFor(() => {
				expect(screen.getByText(/will create child source/)).toBeInTheDocument();
				expect(screen.getByRole('button', { name: 'Create & cite' })).toBeInTheDocument();
			});

			mockPOST
				.mockResolvedValueOnce({ data: CREATED_IPDB_CHILD })
				.mockResolvedValueOnce({ data: CREATED_INSTANCE });
			fireEvent.pointerDown(screen.getByRole('button', { name: 'Create & cite' }));

			await vi.waitFor(() => {
				expect(oncomplete).toHaveBeenCalledWith(`[[cite:${CREATED_INSTANCE.id}]]`);
			});

			expect(mockPOST).toHaveBeenCalledWith('/api/citation-sources/', {
				body: expect.objectContaining({
					parent_id: IPDB_SOURCE.id,
					url: 'https://www.ipdb.org/machine.cgi?id=9999'
				})
			});
			expect(mockPOST).toHaveBeenCalledWith('/api/citation-instances/', {
				body: { citation_source_id: CREATED_IPDB_CHILD.id, locator: '' }
			});
		});

		it('auto-completes when IPDB URL is pasted and child exists', async () => {
			const user = userEvent.setup();
			const { oncomplete } = renderAutocomplete();

			mockGET.mockImplementation((url: string, opts?: { params?: { query?: { q?: string } } }) => {
				if (url === '/api/citation-sources/search/') {
					const q = opts?.params?.query?.q ?? '';
					if (q === 'IPDB' || q.includes('ipdb.org'))
						return Promise.resolve({ data: [IPDB_SOURCE] });
					return Promise.resolve({ data: [] });
				}
				if (url === '/api/citation-sources/{source_id}/children/')
					return Promise.resolve({ data: [IPDB_CHILD] });
				return Promise.resolve({ data: [] });
			});
			mockPOST.mockResolvedValueOnce({ data: CREATED_INSTANCE });

			const input = getSearchInput();
			input.focus();
			await user.keyboard('https://www.ipdb.org/machine.cgi?id=4836');

			await vi.waitFor(() => {
				expect(screen.getByRole('option', { name: /IPDB Machine 4836/ })).toBeInTheDocument();
			});

			fireEvent.pointerDown(screen.getByRole('option', { name: /IPDB Machine 4836/ }));

			// Should auto-complete through identify stage to citation
			await vi.waitFor(() => {
				expect(oncomplete).toHaveBeenCalledWith(`[[cite:${CREATED_INSTANCE.id}]]`);
			});

			expect(mockPOST).toHaveBeenCalledWith('/api/citation-instances/', {
				body: { citation_source_id: IPDB_CHILD.id, locator: '' }
			});
		});
	});
});
