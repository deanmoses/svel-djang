import { describe, expect, it, vi } from 'vitest';
import { load } from './+page.server';

const MOCK_CHANGESETS = [
	{
		id: 1,
		created_at: '2025-01-01T00:00:00Z',
		user: { id: 1, username: 'admin' },
		changes: []
	}
];

describe('model edit-history SSR route', () => {
	it('loads edit history from the backend API', async () => {
		const fetch = vi.fn().mockResolvedValue(
			new Response(JSON.stringify(MOCK_CHANGESETS), {
				status: 200,
				headers: { 'Content-Type': 'application/json' }
			})
		);

		const result = await load({
			fetch,
			url: new URL('http://localhost:5173/models/medieval-madness/edit-history'),
			params: { slug: 'medieval-madness' }
		} as unknown as Parameters<typeof load>[0]);

		expect(result).toEqual({
			changesets: MOCK_CHANGESETS,
			entityType: 'machinemodel',
			slug: 'medieval-madness'
		});
		const request = fetch.mock.calls[0]?.[0];
		expect(request).toBeInstanceOf(Request);
		expect(request.url).toBe(
			'http://localhost:5173/api/edit-history/machinemodel/medieval-madness/'
		);
	});

	it('throws on backend failure', async () => {
		const fetch = vi.fn().mockResolvedValue(new Response('Server error', { status: 500 }));

		await expect(
			load({
				fetch,
				url: new URL('http://localhost:5173/models/medieval-madness/edit-history'),
				params: { slug: 'medieval-madness' }
			} as unknown as Parameters<typeof load>[0])
		).rejects.toMatchObject({ status: 500 });
	});
});
