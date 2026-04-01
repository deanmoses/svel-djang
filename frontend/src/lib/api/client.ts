import createClient from 'openapi-fetch';
import type { paths } from './schema';

export function getCsrfToken(): string | undefined {
	const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
	return match?.[1];
}

const client = createClient<paths>({
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

export default client;
