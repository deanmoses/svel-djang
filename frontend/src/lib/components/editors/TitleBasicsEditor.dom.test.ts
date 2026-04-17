import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TitleBasicsEditorFixture from './TitleBasicsEditor.fixture.svelte';

const { GET, PATCH } = vi.hoisted(() => ({
	GET: vi.fn(),
	PATCH: vi.fn()
}));

const { invalidateAll } = vi.hoisted(() => ({
	invalidateAll: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: { GET, PATCH }
}));

vi.mock('$app/navigation', () => ({
	invalidateAll
}));

const FRANCHISES = {
	data: [
		{ slug: 'addams-family', name: 'Addams Family', title_count: 2 },
		{ slug: 'star-wars', name: 'Star Wars', title_count: 5 }
	]
};

const SERIES = {
	data: [{ slug: 'addams-series', name: 'Addams Series', title_count: 2 }]
};

const INITIAL_TITLE = {
	name: 'The Addams Family',
	slug: 'addams-family',
	franchise: { slug: 'addams-family' },
	series: null,
	abbreviations: ['TAF']
};

function mockGetResponses() {
	GET.mockImplementation(async (path: string) => {
		if (path === '/api/franchises/all/') return FRANCHISES;
		if (path === '/api/series/') return SERIES;
		throw new Error(`Unexpected GET ${path}`);
	});
}

describe('TitleBasicsEditor dirty-state contract', () => {
	beforeEach(() => {
		GET.mockReset();
		PATCH.mockReset();
		invalidateAll.mockReset();
		mockGetResponses();
	});

	it('reports clean state initially and dirty state after editing', async () => {
		const user = userEvent.setup();
		render(TitleBasicsEditorFixture, {
			props: { initialData: INITIAL_TITLE }
		});

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('false');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('false');

		await user.clear(screen.getByLabelText('Name'));
		await user.type(screen.getByLabelText('Name'), 'The Addams Family Gold');

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('true');
	});

	it('PATCHes /api/titles/{slug}/claims/ with only the changed name', async () => {
		const user = userEvent.setup();
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);
		render(TitleBasicsEditorFixture, {
			props: { initialData: INITIAL_TITLE }
		});

		await user.clear(screen.getByLabelText('Name'));
		await user.type(screen.getByLabelText('Name'), 'Addams Family');

		await user.click(screen.getByRole('button', { name: 'Save' }));

		expect(PATCH).toHaveBeenCalledOnce();
		expect(PATCH).toHaveBeenCalledWith('/api/titles/{slug}/claims/', {
			params: { path: { slug: 'addams-family' } },
			body: { fields: { name: 'Addams Family' }, note: '' }
		});
	});
});
