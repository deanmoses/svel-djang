import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ManufacturerFilterSidebarFixture from './ManufacturerFilterSidebar.fixture.svelte';

async function selectFirstSearchableOption(
	user: ReturnType<typeof userEvent.setup>,
	label: RegExp
) {
	const input = screen.getByRole('combobox', { name: label });
	await user.click(input);
	await user.keyboard('{ArrowDown}{Enter}');

	return input;
}

function renderSidebar() {
	return render(ManufacturerFilterSidebarFixture);
}

describe('ManufacturerFilterSidebar', () => {
	it('updates the visible controls when filters change', async () => {
		const user = userEvent.setup();
		renderSidebar();

		const locationInput = await selectFirstSearchableOption(user, /location/i);
		expect(locationInput).toHaveValue('USA');

		const yearFrom = screen.getByLabelText('Year from') as HTMLInputElement;
		const yearTo = screen.getByLabelText('Year to') as HTMLInputElement;
		fireEvent.change(yearFrom, { target: { value: '1990' } });
		fireEvent.change(yearTo, { target: { value: '1995' } });
		expect(yearFrom).toHaveValue(1990);
		expect(yearTo).toHaveValue(1995);

		await user.click(screen.getByRole('button', { name: /solid state/i }));
		await vi.waitFor(() => {
			expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
		});
		expect(screen.getByRole('button', { name: /solid state/i })).toHaveAttribute(
			'aria-pressed',
			'true'
		);
	});

	it('resets all visible controls when Clear all is clicked', async () => {
		const user = userEvent.setup();
		renderSidebar();

		await selectFirstSearchableOption(user, /location/i);
		const yearFrom = screen.getByLabelText('Year from') as HTMLInputElement;
		const yearTo = screen.getByLabelText('Year to') as HTMLInputElement;
		fireEvent.change(yearFrom, { target: { value: '1990' } });
		fireEvent.change(yearTo, { target: { value: '1995' } });
		await user.click(screen.getByRole('button', { name: /solid state/i }));
		await vi.waitFor(() => {
			expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
		});

		await user.click(screen.getByRole('button', { name: /clear all/i }));

		expect(screen.queryByRole('button', { name: /clear all/i })).not.toBeInTheDocument();
		expect(screen.getByRole('combobox', { name: /location/i })).toHaveValue('');
		expect(yearFrom).toHaveValue(null);
		expect(yearTo).toHaveValue(null);
		expect(screen.getByRole('button', { name: /solid state/i })).toHaveAttribute(
			'aria-pressed',
			'false'
		);
	});
});
