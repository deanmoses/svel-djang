import { describe, expect, it, vi } from 'vitest';
import client, { createApiClient } from './client';

describe('api client', () => {
  it('throws if the default client is used on the server', () => {
    expect(() => client.GET).toThrow(
      'The default API client is browser-only. Server-side routes must use createApiClient(fetch, baseUrl?) instead.',
    );
  });

  it('creates a server-safe client with explicit fetch', async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const apiClient = createApiClient(fetch, 'http://localhost:5173');

    await apiClient.GET('/api/health');

    const request = fetch.mock.calls[0]?.[0];
    expect(request).toBeInstanceOf(Request);
    expect(request.url).toBe('http://localhost:5173/api/health');
  });

  describe('public_id path-param slash preservation', () => {
    function makeClient() {
      const fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
      const apiClient = createApiClient(fetch, 'http://localhost:5173');
      return { fetch, apiClient };
    }

    it('preserves slashes in a multi-segment public_id', async () => {
      const { fetch, apiClient } = makeClient();
      await apiClient.GET('/api/corporate-entities/{public_id}/delete-preview/', {
        params: { path: { public_id: 'usa/il/chicago' } },
      });
      const url = new URL(fetch.mock.calls[0]?.[0].url);
      expect(url.pathname).toBe('/api/corporate-entities/usa/il/chicago/delete-preview/');
    });

    it('composes with CSRF: token attached and body preserved after URL rewrite', async () => {
      vi.stubGlobal('document', { cookie: 'csrftoken=abc123' });
      try {
        const { fetch, apiClient } = makeClient();
        await apiClient.POST('/api/corporate-entities/{public_id}/delete/', {
          params: { path: { public_id: 'usa/il/chicago' } },
          body: { note: 'hello' },
        });
        const request = fetch.mock.calls[0]?.[0] as Request;
        expect(new URL(request.url).pathname).toBe(
          '/api/corporate-entities/usa/il/chicago/delete/',
        );
        expect(request.headers.get('X-CSRFToken')).toBe('abc123');
        expect(await request.text()).toBe(JSON.stringify({ note: 'hello' }));
      } finally {
        vi.unstubAllGlobals();
      }
    });
  });
});
