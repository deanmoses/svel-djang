import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import PageActionBar from './PageActionBar.svelte';

describe('PageActionBar', () => {
	it('renders the page actions with the provided hrefs', () => {
		render(PageActionBar, {
			props: {
				editHref: '/models/medieval-madness/edit',
				historyHref: '/models/medieval-madness/history',
				sourcesHref: '/models/medieval-madness/sources'
			}
		});

		expect(screen.getByRole('navigation', { name: /page actions/i })).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'Edit' })).toHaveAttribute(
			'href',
			'/models/medieval-madness/edit'
		);
		expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute(
			'href',
			'/models/medieval-madness/history'
		);
		expect(screen.getByRole('button', { name: 'Tools' })).toBeInTheDocument();
	});

	it('hides the Edit link when editHref is omitted', () => {
		render(PageActionBar, {
			props: {
				historyHref: '/models/medieval-madness/history',
				sourcesHref: '/models/medieval-madness/sources'
			}
		});

		expect(screen.queryByRole('link', { name: 'Edit' })).not.toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'History' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Tools' })).toBeInTheDocument();
	});

	it('renders an edit sections menu when explicit edit sections are provided', async () => {
		const user = userEvent.setup();

		render(PageActionBar, {
			props: {
				editSections: [
					{
						key: 'overview',
						label: 'Overview',
						href: '/models/medieval-madness/edit/overview'
					},
					{
						key: 'relationships',
						label: 'Relationships',
						href: '/models/medieval-madness/edit/relationships'
					}
				],
				historyHref: '/models/medieval-madness/history',
				sourcesHref: '/models/medieval-madness/sources'
			}
		});

		expect(screen.queryByRole('link', { name: 'Edit' })).not.toBeInTheDocument();
		await user.click(screen.getByRole('button', { name: 'Edit' }));
		expect(screen.getByRole('menuitem', { name: 'Overview' })).toHaveAttribute(
			'href',
			'/models/medieval-madness/edit/overview'
		);
		expect(screen.getByRole('menuitem', { name: 'Relationships' })).toHaveAttribute(
			'href',
			'/models/medieval-madness/edit/relationships'
		);
	});
});
