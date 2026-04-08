import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MediaGrid from './MediaGrid.svelte';
import { MEDIA_ITEMS, makeMedia } from './media-test-fixtures';

type ObserverEntry = { isIntersecting: boolean };

const observers: Array<{
	callback: (entries: ObserverEntry[]) => void;
	observe: ReturnType<typeof vi.fn>;
	disconnect: ReturnType<typeof vi.fn>;
}> = [];

beforeEach(() => {
	observers.length = 0;
	class MockIntersectionObserver {
		callback: (entries: ObserverEntry[]) => void;
		observe = vi.fn();
		disconnect = vi.fn();

		constructor(callback: (entries: ObserverEntry[]) => void) {
			this.callback = callback;
			observers.push(this);
		}
	}

	vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
});

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('MediaGrid', () => {
	it('filters by category and shows a category-specific empty state', async () => {
		const user = userEvent.setup();
		render(MediaGrid, {
			media: MEDIA_ITEMS,
			categories: ['Cabinet', 'Backglass', 'Playfield']
		});

		await user.click(screen.getByRole('button', { name: /playfield \(0\)/i }));
		expect(screen.getByText('No Playfield images yet.')).toBeInTheDocument();
	});

	it('opens the lightbox from the filtered media set', async () => {
		const user = userEvent.setup();
		const { container } = render(MediaGrid, {
			media: MEDIA_ITEMS,
			categories: ['Cabinet', 'Backglass']
		});

		await user.click(screen.getByRole('button', { name: /backglass \(1\)/i }));
		await user.click(container.querySelector('.media-card') as HTMLElement);

		expect(screen.getByText('1 / 1')).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument();
	});

	it('grows the visible batch when the sentinel intersects', async () => {
		const media = Array.from({ length: 101 }, (_, index) => makeMedia(index + 1));
		const { container } = render(MediaGrid, {
			media,
			categories: ['Cabinet']
		});

		expect(container.querySelectorAll('.media-card')).toHaveLength(100);
		expect(observers).toHaveLength(1);

		observers[0].callback([{ isIntersecting: true }]);

		await vi.waitFor(() => {
			expect(container.querySelectorAll('.media-card')).toHaveLength(101);
		});
	});
});
