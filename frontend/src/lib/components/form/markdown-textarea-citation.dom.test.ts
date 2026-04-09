import { render, screen, fireEvent } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarkdownTextArea from './MarkdownTextArea.svelte';
import { MOCK_SOURCES, CREATED_INSTANCE } from './citation-fixtures';

vi.mock('$lib/api/link-types', async () => {
	const f = await import('./link-types-fixtures');
	return {
		fetchLinkTypes: vi.fn().mockResolvedValue(f.LINK_TYPES),
		searchLinkTargets: vi.fn().mockResolvedValue({ results: f.SEARCH_RESULTS })
	};
});

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

function renderTextArea(label = 'Description') {
	return render(MarkdownTextArea, { label });
}

/**
 * Simulate typing `[[` into a textarea.
 *
 * userEvent treats `[` as a key-descriptor opener, so `[[` is its escape for
 * a single literal `[`. Instead of fighting the parser we set the value
 * directly and fire `input` — we're testing MarkdownTextArea's trigger
 * detection, not the browser's keypress pipeline.
 */
function typeWikilinkTrigger(textarea: HTMLTextAreaElement, prefix = '', suffix = '') {
	const triggerText = `${prefix}[[${suffix}`;
	const cursorPos = prefix.length + 2;

	textarea.focus();
	textarea.value = triggerText;
	textarea.selectionStart = cursorPos;
	textarea.selectionEnd = cursorPos;
	fireEvent.input(textarea);
}

/**
 * Send a keydown to the textarea without clicking it.
 *
 * Clicking the textarea would trigger handleTextareaClick which closes the
 * dropdown — so we fire the keydown event directly on the element.
 */
function sendTextareaKeydown(textarea: HTMLTextAreaElement, key: string) {
	fireEvent.keyDown(textarea, { key });
}

async function waitForTypePicker() {
	await vi.waitFor(() => {
		expect(screen.getByText('Insert link')).toBeInTheDocument();
	});
}

async function enterCitationFlow(
	textarea: HTMLTextAreaElement,
	prefix = '',
	suffix = ''
): Promise<HTMLInputElement> {
	typeWikilinkTrigger(textarea, prefix, suffix);
	await waitForTypePicker();

	sendTextareaKeydown(textarea, 'ArrowDown');
	sendTextareaKeydown(textarea, 'ArrowDown');
	sendTextareaKeydown(textarea, 'Enter');

	await vi.waitFor(() => {
		expect(screen.getByRole('combobox', { name: /search sources/i })).toBeInTheDocument();
	});

	return screen.getByRole('combobox', { name: /search sources/i }) as HTMLInputElement;
}

async function searchCitation(
	user: ReturnType<typeof userEvent.setup>,
	searchInput: HTMLInputElement,
	query = 'pinball'
) {
	searchInput.focus();
	await user.keyboard(query);

	await vi.waitFor(() => {
		expect(
			screen.getByRole('option', { name: new RegExp(MOCK_SOURCES[0].name) })
		).toBeInTheDocument();
	});
}

async function selectFirstCitationResult() {
	// DropdownItem uses onpointerdown (not onclick), so fire pointerDown directly
	// to avoid flaky timing with userEvent.click in jsdom.
	fireEvent.pointerDown(screen.getByRole('option', { name: new RegExp(MOCK_SOURCES[0].name) }));

	return (await screen.findByRole('textbox', {
		name: /citation locator/i
	})) as HTMLInputElement;
}

function expectDropdownClosed() {
	expect(screen.queryByText('Insert link')).not.toBeInTheDocument();
	expect(screen.queryByRole('combobox', { name: /search sources/i })).not.toBeInTheDocument();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MarkdownTextArea citation integration', () => {
	beforeEach(() => {
		mockGET.mockReset().mockResolvedValue({ data: MOCK_SOURCES });
		mockPOST.mockReset();
	});

	it('inserts a citation with a locator through the full textarea flow', async () => {
		const user = userEvent.setup();
		renderTextArea();
		const textarea = screen.getByRole('textbox', { name: /description/i }) as HTMLTextAreaElement;

		const searchInput = await enterCitationFlow(textarea, 'See ', ' after');
		await searchCitation(user, searchInput);
		const locatorInput = await selectFirstCitationResult();

		locatorInput.focus();
		await user.keyboard('p. 42');

		mockPOST.mockResolvedValueOnce({ data: CREATED_INSTANCE });
		fireEvent.pointerDown(screen.getByRole('button', { name: 'Insert' }));

		const expectedCitation = `[[cite:${CREATED_INSTANCE.id}]]`;
		await vi.waitFor(() => {
			expect(textarea).toHaveValue(`See ${expectedCitation} after`);
		});

		expect(textarea.selectionStart).toBe('See '.length + expectedCitation.length);
		expect(textarea.selectionEnd).toBe('See '.length + expectedCitation.length);
		expect(document.activeElement).toBe(textarea);
		expectDropdownClosed();
		expect(mockPOST).toHaveBeenCalledWith('/api/citation-instances/', {
			body: {
				citation_source_id: MOCK_SOURCES[0].id,
				locator: 'p. 42'
			}
		});
	});

	it('inserts a citation with an empty locator when skip is used', async () => {
		const user = userEvent.setup();
		renderTextArea();
		const textarea = screen.getByRole('textbox', { name: /description/i }) as HTMLTextAreaElement;

		const searchInput = await enterCitationFlow(textarea, 'Ref ');
		await searchCitation(user, searchInput);
		await selectFirstCitationResult();

		mockPOST.mockResolvedValueOnce({ data: CREATED_INSTANCE });
		fireEvent.pointerDown(screen.getByRole('button', { name: 'Skip' }));

		await vi.waitFor(() => {
			expect(textarea).toHaveValue(`Ref [[cite:${CREATED_INSTANCE.id}]]`);
		});

		expect(document.activeElement).toBe(textarea);
		expectDropdownClosed();
		expect(mockPOST).toHaveBeenCalledWith('/api/citation-instances/', {
			body: {
				citation_source_id: MOCK_SOURCES[0].id,
				locator: ''
			}
		});
	});

	it('returns to the type picker and resumes textarea keyboard handling after citation back-navigation', async () => {
		renderTextArea();
		const textarea = screen.getByRole('textbox', { name: /description/i }) as HTMLTextAreaElement;

		const searchInput = await enterCitationFlow(textarea);

		searchInput.focus();
		fireEvent.keyDown(searchInput, { key: 'Backspace' });

		await vi.waitFor(() => {
			expect(screen.getByText('Insert link')).toBeInTheDocument();
		});

		expect(document.activeElement).toBe(textarea);

		sendTextareaKeydown(textarea, 'Escape');

		await vi.waitFor(() => {
			expect(screen.queryByText('Insert link')).not.toBeInTheDocument();
		});
	});
});
