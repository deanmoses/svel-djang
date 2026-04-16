import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import OverviewEditorFixture from './OverviewEditor.fixture.svelte';
import { _resetCache } from '$lib/api/link-types';

const { PATCH } = vi.hoisted(() => ({
	PATCH: vi.fn()
}));

const { invalidateAll } = vi.hoisted(() => ({
	invalidateAll: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: { PATCH }
}));

vi.mock('$app/navigation', () => ({
	invalidateAll
}));

describe('OverviewEditor dirty-state contract', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	beforeEach(() => {
		PATCH.mockReset();
		invalidateAll.mockReset();
		_resetCache();
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue({
				ok: true,
				json: async () => []
			})
		);
	});

	it('reports clean state initially and dirty state after editing', async () => {
		const user = userEvent.setup();
		render(OverviewEditorFixture);

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('false');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('false');

		await user.type(screen.getByLabelText('Description'), ' updated');

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('true');
	});
});
