import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SpecificationsEditorFixture from './SpecificationsEditor.fixture.svelte';

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
		technology_generations: [
			{ slug: 'solid-state', label: 'Solid State' },
			{ slug: 'dot-matrix-era', label: 'Dot Matrix Era' }
		],
		technology_subgenerations: [
			{ slug: 'wpc-95', label: 'WPC-95' },
			{ slug: 'system-11', label: 'System 11' }
		],
		display_types: [
			{ slug: 'dmd', label: 'DMD' },
			{ slug: 'lcd', label: 'LCD' }
		],
		display_subtypes: [
			{ slug: 'orange-dmd', label: 'Orange DMD' },
			{ slug: 'color-dmd', label: 'Color DMD' }
		],
		systems: [
			{ slug: 'wpc-95', label: 'WPC-95' },
			{ slug: 'spike-2', label: 'Spike 2' }
		],
		cabinets: [
			{ slug: 'standard', label: 'Standard' },
			{ slug: 'widebody', label: 'Widebody' }
		],
		game_formats: [
			{ slug: 'pinball-machine', label: 'Pinball Machine' },
			{ slug: 'arcade-video', label: 'Arcade Video' }
		]
	}
};

const FIELD_CONSTRAINTS = {
	data: {
		player_count: { min: 1, max: 6, step: 1 },
		flipper_count: { min: 0, max: 8, step: 1 }
	}
};

const INITIAL_MODEL = {
	technology_generation: { slug: 'solid-state' },
	technology_subgeneration: { slug: 'wpc-95' },
	system: { slug: 'wpc-95' },
	display_type: { slug: 'dmd' },
	display_subtype: { slug: 'orange-dmd' },
	cabinet: { slug: 'standard' },
	game_format: { slug: 'pinball-machine' },
	player_count: 4,
	flipper_count: 2,
	production_quantity: '4016'
};

function mockGetResponses() {
	GET.mockImplementation(async (path: string) => {
		if (path === '/api/models/edit-options/') {
			return EDIT_OPTIONS;
		}

		if (path === '/api/field-constraints/{entity_type}') {
			return FIELD_CONSTRAINTS;
		}

		throw new Error(`Unexpected GET ${path}`);
	});
}

function renderEditor(initialModel = INITIAL_MODEL) {
	mockGetResponses();
	return render(SpecificationsEditorFixture, {
		props: { initialModel, slug: 'medieval-madness' }
	});
}

describe('SpecificationsEditor', () => {
	beforeEach(() => {
		GET.mockReset();
		PATCH.mockReset();
		invalidateAll.mockReset();
	});

	it('renders FK dropdowns from edit-options data', async () => {
		const user = userEvent.setup();
		renderEditor();

		await user.click(screen.getByRole('combobox', { name: 'Technology generation' }));
		expect(await screen.findByRole('option', { name: 'Solid State' })).toBeInTheDocument();
		expect(screen.getByRole('option', { name: 'Dot Matrix Era' })).toBeInTheDocument();

		await user.click(screen.getByRole('combobox', { name: 'Cabinet' }));
		expect(await screen.findByRole('option', { name: 'Standard' })).toBeInTheDocument();
		expect(screen.getByRole('option', { name: 'Widebody' })).toBeInTheDocument();
	});

	it('renders number fields (player count, flipper count, production quantity)', () => {
		renderEditor();

		expect(screen.getByLabelText('Players')).toHaveValue(4);
		expect(screen.getByLabelText('Flippers')).toHaveValue(2);
		expect(screen.getByLabelText('Production quantity')).toHaveValue(4016);
	});

	it('reports clean state initially and dirty state after editing', async () => {
		const user = userEvent.setup();
		renderEditor();

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('false');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('false');

		const flippersInput = screen.getByLabelText('Flippers');
		await user.clear(flippersInput);
		await user.type(flippersInput, '3');

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('true');
	});

	it('save() with no changes calls onsaved() without PATCHing', async () => {
		const user = userEvent.setup();
		renderEditor();

		await user.click(screen.getByRole('button', { name: 'Save' }));

		expect(screen.getByTestId('saved-count')).toHaveTextContent('1');
		expect(PATCH).not.toHaveBeenCalled();
	});

	it('save() with a changed field calls PATCH with only the changed fields', async () => {
		const user = userEvent.setup();
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);
		renderEditor();

		const playersInput = screen.getByLabelText('Players');
		await user.clear(playersInput);
		await user.type(playersInput, '6');

		await user.click(screen.getByRole('button', { name: 'Save' }));

		expect(PATCH).toHaveBeenCalledOnce();
		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: { fields: { player_count: 6 }, note: '' }
		});
		expect(screen.getByTestId('saved-count')).toHaveTextContent('1');
	});

	it('save() passes meta (note/citation) through to the PATCH body', async () => {
		const user = userEvent.setup();
		PATCH.mockResolvedValue({ data: {}, error: undefined });
		invalidateAll.mockResolvedValue(undefined);
		renderEditor();

		const flippersInput = screen.getByLabelText('Flippers');
		await user.clear(flippersInput);
		await user.type(flippersInput, '3');

		await user.click(screen.getByRole('button', { name: 'Save with meta' }));

		expect(PATCH).toHaveBeenCalledOnce();
		expect(PATCH).toHaveBeenCalledWith('/api/models/{slug}/claims/', {
			params: { path: { slug: 'medieval-madness' } },
			body: {
				fields: { flipper_count: 3 },
				note: 'Corrected per flyer',
				citation: { citation_instance_id: 42 }
			}
		});
	});
});
