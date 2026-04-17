import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import BasicsEditorFixture from './BasicsEditor.fixture.svelte';

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

const EDIT_OPTIONS = {
	data: {
		corporate_entities: [
			{ slug: 'williams-electronics', label: 'Williams Electronics' },
			{ slug: 'stern-pinball-inc', label: 'Stern Pinball, Inc.' }
		],
		titles: [
			{ slug: 'medieval-madness', label: 'Medieval Madness' },
			{ slug: 'attack-from-mars', label: 'Attack from Mars' }
		]
	}
};

const FIELD_CONSTRAINTS = {
	data: {
		year: { min: 1930, max: 2100, step: 1 }
	}
};

const INITIAL_MODEL = {
	name: 'Medieval Madness',
	slug: 'medieval-madness',
	year: 1997,
	month: 6,
	title: { slug: 'medieval-madness' },
	corporate_entity: { slug: 'williams-electronics' },
	abbreviations: ['MM']
};

function mockGetResponses() {
	GET.mockImplementation(async (path: string) => {
		if (path === '/api/models/edit-options/') return EDIT_OPTIONS;
		if (path === '/api/field-constraints/{entity_type}') return FIELD_CONSTRAINTS;
		throw new Error(`Unexpected GET ${path}`);
	});
}

describe('BasicsEditor dirty-state contract', () => {
	beforeEach(() => {
		GET.mockReset();
		PATCH.mockReset();
		invalidateAll.mockReset();
		mockGetResponses();
	});

	it('reports clean state initially and dirty state after editing', async () => {
		const user = userEvent.setup();
		render(BasicsEditorFixture, {
			props: { initialData: INITIAL_MODEL }
		});

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('false');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('false');

		await user.clear(screen.getByLabelText('Name'));
		await user.type(screen.getByLabelText('Name'), 'Medieval Madness Remake');

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('true');
	});

	it('changing Title marks dirty and PATCHes only the title slug', async () => {
		const user = userEvent.setup();
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);
		render(BasicsEditorFixture, {
			props: { initialData: INITIAL_MODEL }
		});

		await user.click(screen.getByRole('combobox', { name: 'Title' }));
		await user.click(await screen.findByRole('option', { name: 'Attack from Mars' }));

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

		await user.click(screen.getByRole('button', { name: 'Save' }));

		expect(PATCH).toHaveBeenCalledOnce();
		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { title: 'attack-from-mars' }, note: '' }
		});
	});
});
