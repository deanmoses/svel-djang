import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import EntitySources from './EntitySources.test-harness.svelte';

const sampleClaim = {
	source_name: 'IPDB',
	source_slug: 'ipdb',
	user_display: null,
	field_name: 'year',
	value: 1997,
	citation: '',
	created_at: '2026-04-07T00:00:00Z',
	is_winner: true,
	changeset_note: null
};

describe('EntitySources', () => {
	it('renders cited edit cards separately from provenance groups', () => {
		render(EntitySources, {
			props: {
				sources: [sampleClaim],
				evidence: [
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
			}
		});

		expect(screen.getByText('Documented the flyer')).toBeInTheDocument();
		expect(screen.getByText(/Applies to: year, description/i)).toBeInTheDocument();
		expect(screen.getByText('Williams Flyer')).toBeInTheDocument();
		expect(screen.getByRole('heading', { name: 'Sources', level: 1 })).toBeInTheDocument();
		expect(screen.getByText('Single source (1 field)')).toBeInTheDocument();
	});

	it('omits the Evidence section when no cited changesets are supplied', () => {
		render(EntitySources, {
			props: {
				sources: [sampleClaim],
				evidence: []
			}
		});

		expect(screen.getByRole('heading', { name: 'Sources', level: 1 })).toBeInTheDocument();
		expect(screen.queryByText('Evidence')).not.toBeInTheDocument();
	});

	it('defaults evidence to empty when the prop is omitted', () => {
		render(EntitySources, {
			props: { sources: [sampleClaim] }
		});

		expect(screen.getByRole('heading', { name: 'Sources', level: 1 })).toBeInTheDocument();
		expect(screen.queryByText('Evidence')).not.toBeInTheDocument();
	});

	it('renders the no-sources fallback when sources is empty', () => {
		render(EntitySources, {
			props: { sources: [], evidence: [] }
		});

		expect(screen.getByText(/no source data recorded yet/i)).toBeInTheDocument();
	});
});
