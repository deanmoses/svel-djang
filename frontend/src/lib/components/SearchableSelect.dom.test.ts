import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import SearchableSelect from './SearchableSelect.svelte';

const OPTIONS = [
	{ slug: 'stern', label: 'Stern Pinball', count: 5 },
	{ slug: 'bally', label: 'Bally', count: 3 },
	{ slug: 'williams', label: 'Williams', count: 0 }
];

function renderSingle(props: Partial<{ selected: string | null; allowZeroCount: boolean }> = {}) {
	return render(SearchableSelect, {
		options: OPTIONS,
		label: 'Manufacturer',
		placeholder: 'Search manufacturers...',
		selected: null,
		...props
	});
}

function renderMulti(props: Partial<{ selected: string[]; allowZeroCount: boolean }> = {}) {
	return render(SearchableSelect, {
		options: OPTIONS,
		label: 'Manufacturer',
		placeholder: 'Search manufacturers...',
		multi: true,
		selected: [],
		...props
	});
}

function getCombobox() {
	return screen.getByRole('combobox', { name: /manufacturer/i });
}

describe('SearchableSelect', () => {
	it('opens the listbox on focus', async () => {
		const user = userEvent.setup();
		renderSingle();

		await user.click(getCombobox());

		expect(screen.getByRole('listbox')).toBeInTheDocument();
		expect(screen.getByRole('option', { name: /stern pinball/i })).toBeInTheDocument();
	});

	it('filters options from the typed query', async () => {
		const user = userEvent.setup();
		renderSingle();

		await user.click(getCombobox());
		await user.type(getCombobox(), 'st');

		expect(screen.getByRole('option', { name: /stern pinball/i })).toBeInTheDocument();
		expect(screen.queryByRole('option', { name: /bally/i })).not.toBeInTheDocument();
		expect(screen.queryByRole('option', { name: /williams/i })).not.toBeInTheDocument();
	});

	it('supports arrow-key navigation and enter selection', async () => {
		const user = userEvent.setup();
		renderSingle();

		await user.click(getCombobox());
		await user.keyboard('{ArrowDown}{Enter}');

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
		expect(getCombobox()).toHaveValue('Stern Pinball');
		expect(screen.getByRole('button', { name: /clear selection/i })).toBeInTheDocument();
	});

	it('selects an option with pointer down to match the real interaction path', async () => {
		const user = userEvent.setup();
		renderSingle();

		await user.click(getCombobox());

		const option = screen.getByRole('option', { name: /stern pinball/i });
		await fireEvent.pointerDown(option);

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
		expect(getCombobox()).toHaveValue('Stern Pinball');
	});

	it('closes and resets the query on escape', async () => {
		const user = userEvent.setup();
		renderSingle();

		await user.click(getCombobox());
		await user.type(getCombobox(), 'st');
		await user.keyboard('{Escape}');

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
		expect(getCombobox()).toHaveValue('');
		expect(getCombobox()).not.toHaveFocus();
	});

	it('closes on pointer down outside the component', async () => {
		const user = userEvent.setup();
		renderSingle();

		await user.click(getCombobox());
		expect(screen.getByRole('listbox')).toBeInTheDocument();

		fireEvent.pointerDown(document.body);

		expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
		expect(getCombobox()).toHaveValue('');
	});

	it('clears a single selected value with the clear button', async () => {
		const user = userEvent.setup();
		renderSingle({ selected: 'stern' });

		expect(getCombobox()).toHaveValue('Stern Pinball');

		await user.click(screen.getByRole('button', { name: /clear selection/i }));

		expect(getCombobox()).toHaveValue('');
		expect(screen.queryByRole('button', { name: /clear selection/i })).not.toBeInTheDocument();
	});

	it('removes a selected tag in multi-select mode', async () => {
		const user = userEvent.setup();
		renderMulti({ selected: ['stern', 'bally'] });

		expect(screen.getByText('Stern Pinball')).toBeInTheDocument();
		expect(screen.getByText('Bally')).toBeInTheDocument();

		await user.click(screen.getByRole('button', { name: /remove bally/i }));

		expect(screen.queryByText('Bally')).not.toBeInTheDocument();
		expect(screen.getByText('Stern Pinball')).toBeInTheDocument();
	});

	it('marks zero-count options disabled and does not select them by keyboard by default', async () => {
		const user = userEvent.setup();
		renderSingle({ allowZeroCount: false });

		await user.click(getCombobox());
		await user.type(getCombobox(), 'wil');

		const williams = screen.getByRole('option', { name: /williams/i });
		expect(williams).toHaveAttribute('aria-disabled', 'true');

		await user.keyboard('{ArrowDown}{Enter}');

		expect(screen.getByRole('listbox')).toBeInTheDocument();
		expect(getCombobox()).toHaveValue('wil');
		expect(screen.queryByRole('button', { name: /clear selection/i })).not.toBeInTheDocument();
	});

	it('does not leave queued scroll work behind after keyboard navigation unmounts', async () => {
		vi.useFakeTimers();
		try {
			const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
			const rendered = renderSingle();

			await user.click(getCombobox());
			await user.keyboard('{ArrowDown}');

			rendered.unmount();

			expect(vi.getTimerCount()).toBe(0);
		} finally {
			vi.useRealTimers();
		}
	});
});
