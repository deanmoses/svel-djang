/**
 * Two-client API:
 * - Default `client` export: browser-only Proxy. Use in components/effects.
 * - `createServerClient` (from $lib/api/server): server-only factory that
 *   reads INTERNAL_API_BASE_URL so SSR talks to Django over loopback.
 *
 * The underlying createApiClient factory lives in $lib/api/internal/ and
 * is not part of the public API. Use one of the two clients above.
 */

// The factory itself lives in $lib/api/internal/, which an ESLint rule
// bans the rest of the app from reaching into. This file is the sanctioned
// public surface of the api/ folder, so the reach is intentional — it
// powers the default Proxy below and the exported ApiClient type. Do not
// "fix" this by moving the import elsewhere.
import { createApiClient } from './internal/create-client';

export { registerOnPolicyDenied } from './internal/create-client';

export type ApiClient = ReturnType<typeof createApiClient>;

let browserClient: ApiClient | null = null;

function getBrowserClient(): ApiClient {
  if (typeof window === 'undefined') {
    throw new Error(
      'The default API client is browser-only. Server-side routes must use createServerClient(fetch, url, request) from $lib/api/server instead.',
    );
  }
  browserClient ??= createApiClient(window.fetch.bind(window));
  return browserClient;
}

// SSR-safe: importing this module does NOT trigger getBrowserClient().
// The Proxy defers the browser check to property-access time (client.GET(...)),
// which only happens in event handlers and $effect — never during server render.
// Do not replace this Proxy with a direct createApiClient() call at module scope.
const client = new Proxy({} as ApiClient, {
  get(_target, prop, receiver) {
    return Reflect.get(getBrowserClient(), prop, receiver) as ApiClient[keyof ApiClient];
  },
});

export default client;
