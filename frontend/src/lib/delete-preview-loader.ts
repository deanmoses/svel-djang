import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { createApiClient } from '$lib/api/client';
import type { paths } from '$lib/api/schema';

// Entity-segment union derived from the schema's delete-preview routes.
// New linkable entities pick this up automatically when api-gen runs.
type DeletePreviewEntity =
  Extract<
    keyof paths,
    `/api/${string}/{public_id}/delete-preview/`
  > extends `/api/${infer E}/{public_id}/delete-preview/`
    ? E
    : never;

type DeletePreviewResponse<E extends DeletePreviewEntity> =
  paths[`/api/${E}/{public_id}/delete-preview/`] extends {
    get: { responses: { 200: { content: { 'application/json': infer R } } } };
  }
    ? R
    : never;

interface DeletePreviewLoadOptions<E extends DeletePreviewEntity> {
  fetch: typeof fetch;
  // Page URL from the load event. Required because openapi-fetch
  // constructs `new Request(url, ...)` internally, and Node's Request
  // rejects relative URLs during SSR. We pass `url.origin` as the
  // typed client's baseUrl so the path resolves on both SSR and CSR.
  url: URL;
  slug: string;
  entity: E;
  notFoundRedirect: string;
}

export async function loadDeletePreview<E extends DeletePreviewEntity>({
  fetch,
  url,
  slug,
  entity,
  notFoundRedirect,
}: DeletePreviewLoadOptions<E>): Promise<{ preview: DeletePreviewResponse<E>; slug: string }> {
  const endpoint = `/api/${entity}/{public_id}/delete-preview/`;
  const client = createApiClient(fetch, url.origin);

  // Fail-open if /api/auth/me/ itself errors: the SPA auth gate is UX-only,
  // and the backend will reject the actual delete submission anyway.
  const { data: auth } = await client.GET('/api/auth/me/');
  if (auth && !auth.is_authenticated) {
    throw redirect(302, resolve('/login'));
  }

  // openapi-fetch can't resolve a typed response for a path it sees as a
  // dynamic string, so the casts are localized here. `entity` is already
  // statically constrained to DeletePreviewEntity at the call site.
  const { data, error, response } = await client.GET(
    endpoint as never,
    {
      params: { path: { public_id: slug } },
    } as never,
  );
  const status = response.status;
  if (status === 404) {
    throw redirect(302, notFoundRedirect);
  }
  if (error || !data) {
    throw new Error(`Failed to load delete preview (${status})`);
  }

  return { preview: data as DeletePreviewResponse<E>, slug };
}
