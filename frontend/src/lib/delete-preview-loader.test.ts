import { beforeEach, describe, expect, it, vi } from 'vitest';

const GET = vi.fn();

vi.mock('$lib/api/client', () => ({
  createApiClient: () => ({ GET }),
}));

const { loadDeletePreview } = await import('./delete-preview-loader');

function ok<T>(data: T, status = 200) {
  return { data, error: undefined, response: new Response(null, { status }) };
}

function fail(status: number) {
  return {
    data: undefined,
    error: { detail: 'nope' },
    response: new Response(null, { status }),
  };
}

const fetchStub = (() => undefined) as unknown as typeof globalThis.fetch;

beforeEach(() => {
  GET.mockReset();
});

describe('loadDeletePreview', () => {
  it('returns the preview body and slug on success', async () => {
    const preview = { name: 'Theme', changeset_count: 3 };
    GET.mockResolvedValueOnce(ok({ is_authenticated: true })).mockResolvedValueOnce(ok(preview));

    const result = await loadDeletePreview({
      fetch: fetchStub,
      url: new URL('http://localhost/themes/x/delete'),
      slug: 'cosmic',
      entity: 'themes',
      notFoundRedirect: '/themes',
    });

    expect(result).toEqual({ preview, slug: 'cosmic' });
    expect(GET).toHaveBeenNthCalledWith(1, '/api/auth/me/');
    expect(GET).toHaveBeenNthCalledWith(2, '/api/themes/{public_id}/delete-preview/', {
      params: { path: { public_id: 'cosmic' } },
    });
  });

  it('redirects anonymous users to /login', async () => {
    GET.mockResolvedValueOnce(ok({ is_authenticated: false }));

    await expect(
      loadDeletePreview({
        fetch: fetchStub,
        url: new URL('http://localhost/themes/x/delete'),
        slug: 'cosmic',
        entity: 'themes',
        notFoundRedirect: '/themes',
      }),
    ).rejects.toMatchObject({ status: 302, location: '/login' });
  });

  it('redirects to the fallback URL on 404', async () => {
    GET.mockResolvedValueOnce(ok({ is_authenticated: true })).mockResolvedValueOnce(fail(404));

    await expect(
      loadDeletePreview({
        fetch: fetchStub,
        url: new URL('http://localhost/themes/x/delete'),
        slug: 'missing',
        entity: 'themes',
        notFoundRedirect: '/themes',
      }),
    ).rejects.toMatchObject({ status: 302, location: '/themes' });
  });

  it('throws on other non-OK responses', async () => {
    GET.mockResolvedValueOnce(ok({ is_authenticated: true })).mockResolvedValueOnce(fail(500));

    await expect(
      loadDeletePreview({
        fetch: fetchStub,
        url: new URL('http://localhost/themes/x/delete'),
        slug: 'cosmic',
        entity: 'themes',
        notFoundRedirect: '/themes',
      }),
    ).rejects.toThrow(/500/);
  });

  it('falls open when /api/auth/me/ itself errors', async () => {
    const preview = { name: 'Theme', changeset_count: 0 };
    GET.mockResolvedValueOnce(fail(500)).mockResolvedValueOnce(ok(preview));

    const result = await loadDeletePreview({
      fetch: fetchStub,
      url: new URL('http://localhost/themes/x/delete'),
      slug: 'cosmic',
      entity: 'themes',
      notFoundRedirect: '/themes',
    });

    expect(result).toEqual({ preview, slug: 'cosmic' });
  });
});
