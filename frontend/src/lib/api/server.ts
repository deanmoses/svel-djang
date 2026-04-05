/**
 * Server-side API client factory for SSR load functions.
 *
 * Resolves INTERNAL_API_BASE_URL (direct-to-Django in production)
 * with a fallback to the request origin (Vite proxy in dev).
 *
 * Usage in +page.server.ts / +layout.server.ts:
 *
 *   import { createServerClient } from '$lib/api/server';
 *
 *   export const load = async ({ fetch, url, params }) => {
 *       const client = createServerClient(fetch, url);
 *       ...
 *   };
 */
import { env } from '$env/dynamic/private';
import { createApiClient } from './client';

export function createServerClient(fetchImpl: typeof fetch, url: URL) {
	const baseUrl = env.INTERNAL_API_BASE_URL?.trim() || url.origin;
	return createApiClient(fetchImpl, baseUrl);
}
