import createClient from 'openapi-fetch';
import type { paths } from './schema';

export function getCsrfToken(): string | undefined {
	if (typeof document === 'undefined') return undefined;
	const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
	return match?.[1];
}

export function createApiClient(fetchImpl: typeof fetch = fetch, baseUrl = '') {
	const client = createClient<paths>({
		baseUrl,
		fetch: fetchImpl,
		headers: {
			'Content-Type': 'application/json'
		}
	});

	// Add CSRF token to mutating requests
	client.use({
		async onRequest({ request }) {
			const method = request.method.toUpperCase();
			if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
				const token = getCsrfToken();
				if (token) {
					request.headers.set('X-CSRFToken', token);
				}
			}
			return request;
		}
	});

	return client;
}

let browserClient: ReturnType<typeof createApiClient> | null = null;

function getBrowserClient() {
	if (typeof window === 'undefined') {
		throw new Error(
			'The default API client is browser-only. Server-side routes must use createApiClient(fetch, baseUrl?) instead.'
		);
	}
	browserClient ??= createApiClient(window.fetch.bind(window));
	return browserClient;
}

// SSR-safe: importing this module does NOT trigger getBrowserClient().
// The Proxy defers the browser check to property-access time (client.GET(...)),
// which only happens in event handlers and $effect — never during server render.
// Do not replace this Proxy with a direct createApiClient() call at module scope.
const client = new Proxy({} as ReturnType<typeof createApiClient>, {
	get(_target, prop, receiver) {
		return Reflect.get(getBrowserClient(), prop, receiver);
	}
});

export default client;
