import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';
import Page from './+page.svelte';
import { load } from './+page.server';

describe('hello SSR route', () => {
	it('loads the hello message from the backend API', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ message: 'Hello world from Django' }), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		const result = await load({
			fetch,
			url: new URL('http://localhost:5173/hello')
		} as unknown as Parameters<typeof load>[0]);

		expect(result).toEqual({ message: 'Hello world from Django' });
		const request = fetch.mock.calls[0]?.[0];
		expect(request).toBeInstanceOf(Request);
		expect(request.method).toBe('GET');
		expect(request.url).toBe('http://localhost:5173/api/hello/');
	});

	it('renders the message into the initial HTML', () => {
		const { body } = render(Page, {
			props: {
				data: { message: 'Hello world from Django' }
			}
		});

		expect(body).toContain('Hello world from Django');
		expect(body).toContain('This content was rendered on the server.');
	});
});
