import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import Harness from './edit-history-page.test-harness.svelte';

describe('cabinet edit-history page (taxonomy representative)', () => {
	it('wraps EditHistory in FocusContentShell with back link to detail and an Edit History heading', () => {
		const { body } = render(Harness, {
			props: { data: { changesets: [] } }
		});

		expect(body).toContain('href="/cabinets/standard-body"');
		expect(body).toContain('Back');
		expect(body).toContain('<h1>Edit History</h1>');
		expect(body.toLowerCase()).toContain('no edit history yet');
	});
});
