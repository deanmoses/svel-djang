import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import EntityProvenance from './EntityProvenance.svelte';

const { GET } = vi.hoisted(() => ({
	GET: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: { GET }
}));

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason?: unknown) => void;
	const promise = new Promise<T>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

describe('EntityProvenance', () => {
	it('renders cited edit cards separately from provenance groups', async () => {
		GET.mockResolvedValue({
			data: [
				{
					id: 1,
					user_display: 'editor',
					note: 'Documented the flyer',
					created_at: '2026-04-08T00:00:00Z',
					fields: ['year', 'description'],
					citations: [
						{
							source_name: 'Williams Flyer',
							source_type: 'web',
							author: '',
							year: 1993,
							locator: 'p. 2',
							links: [{ url: 'https://example.com/flyer', label: 'Scan' }]
						}
					]
				}
			]
		});

		render(EntityProvenance, {
			props: {
				sources: [
					{
						source_name: 'IPDB',
						source_slug: 'ipdb',
						user_display: null,
						field_name: 'year',
						value: 1997,
						citation: '',
						created_at: '2026-04-07T00:00:00Z',
						is_winner: true,
						changeset_note: null
					}
				],
				entityType: 'title',
				entitySlug: 'medieval-madness'
			}
		});

		expect(await screen.findByText('Documented the flyer')).toBeInTheDocument();
		expect(screen.getByText(/Applies to: year, description/i)).toBeInTheDocument();
		expect(screen.getByText('Williams Flyer')).toBeInTheDocument();
		expect(screen.getByText('Sources')).toBeInTheDocument();
		expect(screen.getByText('Single source (1 field)')).toBeInTheDocument();
	});

	it('falls back cleanly when the evidence request fails', async () => {
		GET.mockRejectedValue(new Error('network failed'));

		render(EntityProvenance, {
			props: {
				sources: [
					{
						source_name: 'IPDB',
						source_slug: 'ipdb',
						user_display: null,
						field_name: 'year',
						value: 1997,
						citation: '',
						created_at: '2026-04-07T00:00:00Z',
						is_winner: true,
						changeset_note: null
					}
				],
				entityType: 'title',
				entitySlug: 'medieval-madness'
			}
		});

		expect(await screen.findByText('Sources')).toBeInTheDocument();
		expect(screen.queryByText('Evidence')).not.toBeInTheDocument();
	});

	it('ignores stale evidence responses after navigation', async () => {
		const first = deferred<{ data: Array<Record<string, unknown>> }>();
		const second = deferred<{ data: Array<Record<string, unknown>> }>();
		GET.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise);

		const { rerender } = render(EntityProvenance, {
			props: {
				sources: [
					{
						source_name: 'IPDB',
						source_slug: 'ipdb',
						user_display: null,
						field_name: 'year',
						value: 1997,
						citation: '',
						created_at: '2026-04-07T00:00:00Z',
						is_winner: true,
						changeset_note: null
					}
				],
				entityType: 'title',
				entitySlug: 'medieval-madness'
			}
		});

		await rerender({
			sources: [
				{
					source_name: 'IPDB',
					source_slug: 'ipdb',
					user_display: null,
					field_name: 'year',
					value: 1997,
					citation: '',
					created_at: '2026-04-07T00:00:00Z',
					is_winner: true,
					changeset_note: null
				}
			],
			entityType: 'title',
			entitySlug: 'attack-from-mars'
		});

		second.resolve({
			data: [
				{
					id: 2,
					user_display: 'editor',
					note: 'Newer response',
					created_at: '2026-04-09T00:00:00Z',
					fields: ['year'],
					citations: []
				}
			]
		});

		expect(await screen.findByText('Newer response')).toBeInTheDocument();

		first.resolve({
			data: [
				{
					id: 1,
					user_display: 'editor',
					note: 'Older response',
					created_at: '2026-04-08T00:00:00Z',
					fields: ['description'],
					citations: []
				}
			]
		});

		expect(screen.queryByText('Older response')).not.toBeInTheDocument();
	});
});
