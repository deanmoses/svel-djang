import { describe, expect, it, vi } from 'vitest';
import client, { createApiClient } from './client';

describe('api client', () => {
	it('throws if the default client is used on the server', () => {
		expect(() => client.GET).toThrow(
			'The default API client is browser-only. Server-side routes must use createApiClient(fetch, baseUrl?) instead.'
		);
	});

	it('creates a server-safe client with explicit fetch', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ ok: true }), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);
		const apiClient = createApiClient(fetch, 'http://localhost:5173');

		await apiClient.GET('/api/health');

		const request = fetch.mock.calls[0]?.[0];
		expect(request).toBeInstanceOf(Request);
		expect(request.url).toBe('http://localhost:5173/api/health');
	});
});
