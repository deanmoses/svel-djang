import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import DescriptionEditorFixture from './DescriptionEditor.fixture.svelte';
import { _resetCache } from '$lib/api/link-types';

describe('DescriptionEditor', () => {
	beforeEach(() => {
		_resetCache();
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue({
				ok: true,
				json: async () => []
			})
		);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('reports clean state initially and dirty state after editing', async () => {
		const user = userEvent.setup();
		render(DescriptionEditorFixture);

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('false');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('false');

		await user.type(screen.getByLabelText('Description'), ' updated');

		expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

		await user.click(screen.getByRole('button', { name: 'Check dirty' }));
		expect(screen.getByTestId('dirty-handle')).toHaveTextContent('true');
	});

	it('calls the injected save function with the edited description when dirty', async () => {
		const user = userEvent.setup();
		render(DescriptionEditorFixture);

		await user.type(screen.getByLabelText('Description'), ' updated');
		await user.click(screen.getByRole('button', { name: 'Save' }));

		expect(screen.getByTestId('last-save-body')).toHaveTextContent(
			JSON.stringify({ fields: { description: 'Original description updated' } })
		);
		expect(screen.getByTestId('saved-count')).toHaveTextContent('1');
	});

	it('skips the save call when clean', async () => {
		const user = userEvent.setup();
		render(DescriptionEditorFixture);

		await user.click(screen.getByRole('button', { name: 'Save' }));

		expect(screen.getByTestId('last-save-body')).toHaveTextContent('null');
		expect(screen.getByTestId('saved-count')).toHaveTextContent('1');
	});
});
