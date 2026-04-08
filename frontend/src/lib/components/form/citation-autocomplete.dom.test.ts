import { render, screen, fireEvent } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, it, expect, vi } from 'vitest';
import CitationAutocomplete from './CitationAutocomplete.svelte';
import { MOCK_SOURCES, CREATED_SOURCE, CREATED_INSTANCE } from './citation-fixtures';

// vi.hoisted runs before vi.mock hoisting, so mockGET/mockPOST are
// available inside the factory AND in test code — no type-casting needed.
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

function renderCitation() {
	const oncomplete = vi.fn();
	const oncancel = vi.fn();
	const onback = vi.fn();
	const result = render(CitationAutocomplete, { oncomplete, oncancel, onback });
	return { ...result, oncomplete, oncancel, onback };
}

/** Type a query into the search input and wait for results to appear. */
async function searchFor(query: string) {
	const ctx = renderCitation();
	const user = userEvent.setup();
	const input = screen.getByRole('combobox', { name: /search sources/i });

	await user.click(input);
	await user.keyboard(query);

	await vi.waitFor(() => {
		expect(
			screen.getByText('The Encyclopedia of Pinball \u2014 Richard Bueschel, 1996')
		).toBeInTheDocument();
	});

	return { ...ctx, user, input };
}

/** Search for a query → select the first result → arrive at locator stage. */
async function openLocator() {
	const ctx = await searchFor('pinball');
	const { user } = ctx;

	// ArrowDown to first result, Enter to select
	await user.keyboard('{ArrowDown}');
	await user.keyboard('{Enter}');

	await vi.waitFor(() => {
		expect(screen.getByText(/citing:/i)).toBeInTheDocument();
	});

	const locatorInput = screen.getByRole('textbox', { name: /citation locator/i });
	return { ...ctx, locatorInput };
}

/** Search for a query → navigate to "Create new" → arrive at create stage. */
async function openCreate(query = 'New Source') {
	mockGET.mockResolvedValue({ data: [] });

	const ctx = renderCitation();
	const user = userEvent.setup();
	const input = screen.getByRole('combobox', { name: /search sources/i });

	await user.click(input);
	await user.keyboard(query);

	await vi.waitFor(() => {
		expect(screen.getByText(/no matches/i)).toBeInTheDocument();
	});

	// "Create new" is the only option — ArrowDown + Enter
	await user.keyboard('{ArrowDown}');
	await user.keyboard('{Enter}');

	await vi.waitFor(() => {
		expect(screen.getByText('New source')).toBeInTheDocument();
	});

	return { ...ctx, user };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CitationAutocomplete', () => {
	afterEach(() => {
		mockGET.mockReset().mockResolvedValue({ data: MOCK_SOURCES });
		mockPOST.mockReset();
	});

	// -----------------------------------------------------------------------
	// Search stage
	// -----------------------------------------------------------------------

	describe('search stage', () => {
		it('shows "Type to search sources..." prompt when query is empty', () => {
			renderCitation();
			expect(screen.getByText('Type to search sources...')).toBeInTheDocument();
		});

		it('shows search results after typing', async () => {
			await searchFor('pinball');

			expect(
				screen.getByText('The Encyclopedia of Pinball \u2014 Richard Bueschel, 1996')
			).toBeInTheDocument();
			expect(screen.getByText('Pinball Magazine')).toBeInTheDocument();
			// Verify GET was called with the query
			expect(mockGET).toHaveBeenCalled();
		});

		it('shows "No matches" when search returns empty', async () => {
			mockGET.mockResolvedValue({ data: [] });

			const user = userEvent.setup();
			renderCitation();

			await user.click(screen.getByRole('combobox', { name: /search sources/i }));
			await user.keyboard('nonexistent');

			await vi.waitFor(() => {
				expect(screen.getByText('No matches')).toBeInTheDocument();
			});
		});

		it('shows "Create new" option when query is non-empty', async () => {
			await searchFor('pinball');

			expect(screen.getByText(/create "pinball"/i)).toBeInTheDocument();
		});

		it('"Create new" is navigable via ArrowDown past results', async () => {
			const { user } = await searchFor('pinball');

			// activeIndex starts at -1, so we need length+1 presses to reach "Create new"
			for (let i = 0; i <= MOCK_SOURCES.length; i++) {
				await user.keyboard('{ArrowDown}');
			}

			// The "Create new" item should be active
			const options = screen.getAllByRole('option');
			const createOption = options[options.length - 1];
			expect(createOption).toHaveAttribute('aria-selected', 'true');
		});

		it('selecting a result transitions to locator stage', async () => {
			const { user } = await searchFor('pinball');

			await user.keyboard('{ArrowDown}');
			await user.keyboard('{Enter}');

			await vi.waitFor(() => {
				expect(screen.getByText(/citing:/i)).toBeInTheDocument();
				expect(screen.getByText(new RegExp(MOCK_SOURCES[0].name))).toBeInTheDocument();
			});
		});

		it('calls onback on Backspace with empty input', async () => {
			const user = userEvent.setup();
			const { onback } = renderCitation();
			const input = screen.getByRole('combobox', { name: /search sources/i });

			await user.click(input);
			await user.keyboard('{Backspace}');

			expect(onback).toHaveBeenCalledOnce();
		});

		it('calls onback on ArrowLeft at position 0', async () => {
			const user = userEvent.setup();
			const { onback } = renderCitation();
			const input = screen.getByRole('combobox', { name: /search sources/i });

			await user.click(input);
			await user.keyboard('{ArrowLeft}');

			expect(onback).toHaveBeenCalledOnce();
		});

		it('calls oncancel on Escape', async () => {
			const user = userEvent.setup();
			const { oncancel } = renderCitation();
			const input = screen.getByRole('combobox', { name: /search sources/i });

			await user.click(input);
			await user.keyboard('{Escape}');

			expect(oncancel).toHaveBeenCalledOnce();
		});
	});

	// -----------------------------------------------------------------------
	// Create stage
	// -----------------------------------------------------------------------

	describe('create stage', () => {
		it('pre-fills name from search query', async () => {
			await openCreate('My New Book');

			const nameInput = screen.getByPlaceholderText('Name') as HTMLInputElement;
			expect(nameInput.value).toBe('My New Book');
		});

		it('type chips toggle between book/magazine/web and preventDefault to preserve focus', async () => {
			await openCreate();

			// Default is book
			const bookChip = screen.getByRole('button', { name: 'book' });
			expect(bookChip).toHaveClass('selected');

			// Click magazine — handler must preventDefault so browser won't steal focus
			// fireEvent returns false (via dispatchEvent) when preventDefault was called
			const magPrevented = await fireEvent.pointerDown(
				screen.getByRole('button', { name: 'magazine' })
			);
			expect(magPrevented).toBe(false);
			expect(screen.getByRole('button', { name: 'magazine' })).toHaveClass('selected');
			expect(bookChip).not.toHaveClass('selected');

			// Click web
			const webPrevented = await fireEvent.pointerDown(screen.getByRole('button', { name: 'web' }));
			expect(webPrevented).toBe(false);
			expect(screen.getByRole('button', { name: 'web' })).toHaveClass('selected');
		});

		it('shows author field for book, hides for web', async () => {
			await openCreate();

			// Book (default) — author visible
			expect(screen.getByPlaceholderText(/author/i)).toBeInTheDocument();

			// Switch to web — author hidden
			fireEvent.pointerDown(screen.getByRole('button', { name: 'web' }));
			expect(screen.queryByPlaceholderText(/author/i)).not.toBeInTheDocument();
		});

		it('shows URL field for web, hides for book', async () => {
			await openCreate();

			// Book (default) — no URL field
			expect(screen.queryByPlaceholderText('URL')).not.toBeInTheDocument();

			// Switch to web — URL visible
			fireEvent.pointerDown(screen.getByRole('button', { name: 'web' }));
			expect(screen.getByPlaceholderText('URL')).toBeInTheDocument();
		});

		it('shows error when name is empty', async () => {
			const { user } = await openCreate();

			// Clear the pre-filled name
			const nameInput = screen.getByPlaceholderText('Name');
			await user.clear(nameInput);

			// Submit
			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			expect(screen.getByText('Name is required.')).toBeInTheDocument();
		});

		it('shows error when web type has no URL', async () => {
			const { user } = await openCreate();

			// Switch to web type
			fireEvent.pointerDown(screen.getByRole('button', { name: 'web' }));

			// Submit without URL
			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			expect(screen.getByText('URL is required for web sources.')).toBeInTheDocument();
		});

		it('successful POST transitions to locator stage', async () => {
			mockPOST.mockResolvedValueOnce({
				data: CREATED_SOURCE,
				error: undefined
			});

			const { user } = await openCreate();

			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			await vi.waitFor(() => {
				expect(screen.getByText(`Citing: ${CREATED_SOURCE.name}`)).toBeInTheDocument();
			});

			expect(mockPOST).toHaveBeenCalledWith(
				'/api/citation-sources/',
				expect.objectContaining({
					body: expect.objectContaining({ name: 'New Source', source_type: 'book' })
				})
			);
		});

		it('API error displays error message for string error', async () => {
			mockPOST.mockResolvedValueOnce({
				data: undefined,
				error: 'Something went wrong'
			});

			const { user } = await openCreate();

			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			await vi.waitFor(() => {
				expect(screen.getByText('Something went wrong')).toBeInTheDocument();
			});
		});

		it('API error displays fallback message for non-string error', async () => {
			mockPOST.mockResolvedValueOnce({
				data: undefined,
				error: { detail: 'bad request' }
			});

			const { user } = await openCreate();

			await user.click(screen.getByRole('button', { name: /create & cite/i }));

			await vi.waitFor(() => {
				expect(screen.getByText('Failed to create source.')).toBeInTheDocument();
			});
		});

		it('back button returns to search', async () => {
			await openCreate();

			// Click the back button (aria-label="Back")
			fireEvent.pointerDown(screen.getByRole('button', { name: /back/i }));

			await vi.waitFor(() => {
				expect(screen.getByRole('combobox', { name: /search sources/i })).toBeInTheDocument();
			});
		});

		it('auto-focuses the name input', async () => {
			await openCreate();

			await vi.waitFor(() => {
				expect(document.activeElement).toBe(screen.getByPlaceholderText('Name'));
			});
		});

		it('Escape calls oncancel', async () => {
			const { user, oncancel } = await openCreate();

			// Wait for auto-focus so Escape reaches the form's onkeydown handler
			await vi.waitFor(() => {
				expect(document.activeElement).toBe(screen.getByPlaceholderText('Name'));
			});

			await user.keyboard('{Escape}');

			expect(oncancel).toHaveBeenCalledOnce();
		});
	});

	// -----------------------------------------------------------------------
	// Locator stage
	// -----------------------------------------------------------------------

	describe('locator stage', () => {
		it('header shows selected source name', async () => {
			await openLocator();

			expect(screen.getByText(`Citing: ${MOCK_SOURCES[0].name}`)).toBeInTheDocument();
		});

		it('Enter submits and calls oncomplete with [[cite:ID]]', async () => {
			mockPOST.mockResolvedValueOnce({ data: CREATED_INSTANCE });
			const { user, oncomplete, locatorInput } = await openLocator();

			await user.click(locatorInput);
			await user.keyboard('p. 42');
			await user.keyboard('{Enter}');

			await vi.waitFor(() => {
				expect(oncomplete).toHaveBeenCalledOnce();
			});
			expect(oncomplete).toHaveBeenCalledWith(`[[cite:${CREATED_INSTANCE.id}]]`);

			expect(mockPOST).toHaveBeenCalledWith(
				'/api/citation-instances/',
				expect.objectContaining({
					body: { citation_source_id: MOCK_SOURCES[0].id, locator: 'p. 42' }
				})
			);
		});

		it('Skip submits with empty locator', async () => {
			mockPOST.mockResolvedValueOnce({ data: CREATED_INSTANCE });
			const { oncomplete } = await openLocator();

			// Click Skip button via pointerDown (matches component's onpointerdown)
			fireEvent.pointerDown(screen.getByRole('button', { name: /skip/i }));

			await vi.waitFor(() => {
				expect(oncomplete).toHaveBeenCalledOnce();
			});
			expect(oncomplete).toHaveBeenCalledWith(`[[cite:${CREATED_INSTANCE.id}]]`);
		});

		it('Backspace on empty locator returns to search', async () => {
			const { user, locatorInput } = await openLocator();

			await user.click(locatorInput);
			await user.keyboard('{Backspace}');

			await vi.waitFor(() => {
				expect(screen.getByRole('combobox', { name: /search sources/i })).toBeInTheDocument();
			});
		});

		it('ArrowLeft at position 0 returns to search', async () => {
			const { user, locatorInput } = await openLocator();

			await user.click(locatorInput);
			await user.keyboard('{ArrowLeft}');

			await vi.waitFor(() => {
				expect(screen.getByRole('combobox', { name: /search sources/i })).toBeInTheDocument();
			});
		});

		it('API error displays error message', async () => {
			mockPOST.mockResolvedValueOnce({
				data: undefined,
				error: 'Server error'
			});

			const { user } = await searchFor('pinball');

			// Select first result to go to locator
			await user.keyboard('{ArrowDown}');
			await user.keyboard('{Enter}');

			await vi.waitFor(() => {
				expect(screen.getByText(/citing:/i)).toBeInTheDocument();
			});

			const locatorInput = screen.getByRole('textbox', { name: /citation locator/i });
			await user.click(locatorInput);
			await user.keyboard('{Enter}');

			await vi.waitFor(() => {
				expect(screen.getByText('Failed to create citation.')).toBeInTheDocument();
			});
		});
	});
});
