import { render } from 'svelte/server';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { pageState } = vi.hoisted(() => ({
	pageState: {
		params: { slug: 'williams', section: 'name' },
		url: new URL('http://localhost:5173/manufacturers/williams/edit/name')
	}
}));

vi.mock('$app/state', () => ({
	page: pageState
}));

import Harness from './layout.test-harness.svelte';

describe('manufacturer edit section layout', () => {
	beforeEach(() => {
		pageState.params.slug = 'williams';
		pageState.params.section = 'name';
		pageState.url = new URL('http://localhost:5173/manufacturers/williams/edit/name');
	});

	it('does not server-render the mobile edit shell before viewport detection', () => {
		const { body } = render(Harness);

		expect(body).not.toContain('>Back<');
		expect(body).not.toContain('Child content');
	});
});
