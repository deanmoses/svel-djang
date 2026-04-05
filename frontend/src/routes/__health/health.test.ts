import { describe, expect, it, vi } from 'vitest';
import { GET } from './+server';

describe('readiness endpoint', () => {
	it('checks Django through the server-side API path', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ status: 'ok' }), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		const response = await GET({
			fetch,
			url: new URL('http://localhost:5173/__health')
		} as unknown as Parameters<typeof GET>[0]);

		expect(response.status).toBe(200);
		await expect(response.json()).resolves.toEqual({ status: 'ok' });

		const request = fetch.mock.calls[0]?.[0];
		expect(request).toBeInstanceOf(Request);
		expect(request.url).toBe('http://localhost:5173/api/health');
	});
});
