import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import Harness from './edit-history-page.test-harness.svelte';

describe('title edit-history page', () => {
	it('wraps EditHistory in FocusContentShell with back link to detail and an Edit History heading', () => {
		const { body } = render(Harness, {
			props: { data: { changesets: [] } }
		});

		expect(body).toContain('href="/titles/medieval-madness"');
		expect(body).toContain('Back');
		expect(body).toContain('<h1>Edit History</h1>');
		// EditHistory empty-state passes through.
		expect(body.toLowerCase()).toContain('no edit history yet');
	});
});
