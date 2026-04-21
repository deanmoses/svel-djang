import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockGet, authMock } = vi.hoisted(() => ({
	mockGet: vi.fn(),
	authMock: { isAuthenticated: true, load: () => Promise.resolve() }
}));

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/paths', () => ({ resolve: (p: string) => p }));
vi.mock('$lib/api/client', () => ({
	default: { GET: mockGet }
}));
vi.mock('$lib/auth.svelte', () => ({ auth: authMock }));

import Page from './+page.svelte';

const SYSTEMS = [
	{
		name: 'SPIKE',
		slug: 'spike',
		manufacturer: { slug: 'stern', name: 'Stern' },
		machine_count: 42
	},
	{
		name: 'WPC-95',
		slug: 'wpc-95',
		manufacturer: { slug: 'williams', name: 'Williams' },
		machine_count: 30
	},
	{
		name: 'Whitestar',
		slug: 'whitestar',
		manufacturer: { slug: 'stern', name: 'Stern' },
		machine_count: 12
	}
];

async function renderAndWait() {
	mockGet.mockResolvedValue({ data: SYSTEMS });
	render(Page);
	// createAsyncLoader resolves on the next tick; wait for a known row.
	await screen.findByText('SPIKE');
}

describe('systems list route', () => {
	beforeEach(() => {
		mockGet.mockReset();
		authMock.isAuthenticated = true;
	});

	it('renders all systems with manufacturer and machine count', async () => {
		await renderAndWait();
		expect(screen.getByText('SPIKE')).toBeInTheDocument();
		expect(screen.getByText('WPC-95')).toBeInTheDocument();
		expect(screen.getByText('Whitestar')).toBeInTheDocument();
		// Two systems show "Stern" as their row-level manufacturer label
		// (a third "Stern" lives inside the filter <select> options).
		expect(screen.getAllByText('Stern').length).toBeGreaterThanOrEqual(2);
		expect(screen.getByText('42 machines')).toBeInTheDocument();
		expect(screen.getByText('30 machines')).toBeInTheDocument();
	});

	it('derives manufacturer options from visible systems', async () => {
		await renderAndWait();
		const select = screen.getByLabelText('Manufacturer') as HTMLSelectElement;
		const optionLabels = Array.from(select.options).map((o) => o.textContent);
		// First entry is "All manufacturers"; Stern + Williams follow in
		// alphabetical order. Stern appears once despite two systems owning it.
		expect(optionLabels).toEqual(['All manufacturers', 'Stern', 'Williams']);
	});

	it('manufacturer filter narrows the rendered list', async () => {
		const user = userEvent.setup();
		await renderAndWait();

		const select = screen.getByLabelText('Manufacturer') as HTMLSelectElement;
		await user.selectOptions(select, 'williams');

		expect(screen.getByText('WPC-95')).toBeInTheDocument();
		expect(screen.queryByText('SPIKE')).not.toBeInTheDocument();
		expect(screen.queryByText('Whitestar')).not.toBeInTheDocument();
	});

	it('shows "+ New System" in the action menu when authenticated', async () => {
		const user = userEvent.setup();
		await renderAndWait();
		// The action-menu trigger is labeled "Edit" by EditSectionMenu's default.
		await user.click(screen.getByRole('button', { name: 'Edit' }));
		expect(screen.getByRole('menuitem', { name: /\+ New System/ })).toBeInTheDocument();
	});

	it('hides the action-menu trigger entirely when unauthenticated', async () => {
		authMock.isAuthenticated = false;
		mockGet.mockResolvedValue({ data: SYSTEMS });
		render(Page);
		await screen.findByText('SPIKE');
		// The trigger itself is gated on auth, so there is no Edit button to
		// click — and therefore no way to reveal the create item.
		expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
	});
});
