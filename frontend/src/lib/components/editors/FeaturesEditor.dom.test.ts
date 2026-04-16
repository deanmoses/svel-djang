import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import FeaturesEditorFixture from './FeaturesEditor.fixture.svelte';

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
		themes: [
			{ slug: 'medieval', label: 'Medieval' },
			{ slug: 'fantasy', label: 'Fantasy' }
		],
		tags: [
			{ slug: 'classic', label: 'Classic' },
			{ slug: 'widebody', label: 'Widebody' }
		],
		reward_types: [
			{ slug: 'replay', label: 'Replay' },
			{ slug: 'extra-ball', label: 'Extra Ball' }
		],
		gameplay_features: [
			{ slug: 'multiball', label: 'Multiball' },
			{ slug: 'ramps', label: 'Ramps' }
		]
	}
};

const INITIAL_MODEL = {
	themes: [{ slug: 'medieval' }],
	tags: [{ slug: 'classic' }],
	reward_types: [{ slug: 'replay' }],
	gameplay_features: [{ slug: 'multiball', count: 3 }]
};

describe('FeaturesEditor dirty-state contract', () => {
	beforeEach(() => {
		GET.mockReset();
		PATCH.mockReset();
		invalidateAll.mockReset();
		GET.mockImplementation(async (path: string) => {
			if (path === '/api/models/edit-options/') return EDIT_OPTIONS;
			throw new Error(`Unexpected GET ${path}`);
		});
	});

	it('reports clean state initially and dirty state after editing', async () => {
		const user = userEvent.setup();
		render(FeaturesEditorFixture, {
			props: { initialModel: INITIAL_MODEL }
		});

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('false');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('false');

		await user.click(screen.getByRole('button', { name: '×' }));

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('true');
	});
});
