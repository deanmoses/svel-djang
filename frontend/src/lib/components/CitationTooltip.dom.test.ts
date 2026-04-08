import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CitationTooltipFixture from './CitationTooltip.fixture.svelte';

const { GET } = vi.hoisted(() => ({
	GET: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	default: {
		GET
	}
}));

function rect({
	left,
	top,
	width,
	height
}: {
	left: number;
	top: number;
	width: number;
	height: number;
}) {
	return {
		left,
		top,
		width,
		height,
		right: left + width,
		bottom: top + height,
		x: left,
		y: top,
		toJSON() {
			return this;
		}
	} as DOMRect;
}

let anchorRect = rect({ left: 100, top: 160, width: 24, height: 16 });

beforeEach(() => {
	GET.mockReset().mockResolvedValue({
		data: [
			{
				id: 1,
				source_name: 'Pinball Book',
				source_type: 'book',
				author: 'Jane Doe',
				year: 1992,
				locator: 'p. 42',
				links: [{ url: 'https://example.com/book', label: 'Source link' }]
			},
			{
				id: 2,
				source_name: 'Magazine Interview',
				source_type: 'magazine',
				author: 'John Roe',
				year: 1995,
				locator: '',
				links: []
			}
		]
	});
	anchorRect = rect({ left: 100, top: 160, width: 24, height: 16 });
	vi.useFakeTimers();
	vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
		this: HTMLElement
	) {
		if (this.matches?.('sup[data-cite-id]')) return anchorRect;
		if (this.getAttribute?.('role') === 'tooltip') {
			return rect({ left: 0, top: 0, width: 180, height: 80 });
		}
		return rect({ left: 0, top: 0, width: 0, height: 0 });
	});
});

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
});

import type { InlineCitation } from './citation-tooltip';

function renderTooltip(html: string, citations?: InlineCitation[]) {
	return render(CitationTooltipFixture, { html, htmlSignal: html, citations });
}

function getCitation(id: string) {
	return document.querySelector(`sup[data-cite-id="${id}"]`) as HTMLElement;
}

describe('CitationTooltip', () => {
	it('scans citations and fetches each missing id only once', async () => {
		const initialHtml =
			'<p>One <sup data-cite-id="1" tabindex="0">[1]</sup> and two <sup data-cite-id="1" tabindex="0">[1]</sup> plus <sup data-cite-id="2" tabindex="0">[2]</sup>.</p>';
		const rendered = renderTooltip(initialHtml);

		await vi.waitFor(() => {
			expect(GET).toHaveBeenCalledWith('/api/citation-instances/batch/', {
				params: { query: { ids: '1,2' } }
			});
		});

		await rendered.rerender({
			html: '<p>Updated <sup data-cite-id="1" tabindex="0">[1]</sup> and <sup data-cite-id="2" tabindex="0">[2]</sup>.</p>',
			htmlSignal: 'updated'
		});

		await vi.advanceTimersByTimeAsync(0);
		expect(GET).toHaveBeenCalledTimes(1);
	});

	it('shows the tooltip on hover and hides it after the hide delay', async () => {
		renderTooltip('<p>Hover <sup data-cite-id="1" tabindex="0">[1]</sup>.</p>');
		await vi.waitFor(() => expect(GET).toHaveBeenCalledTimes(1));

		await fireEvent.mouseEnter(getCitation('1'));
		const tooltip = await screen.findByRole('tooltip');
		expect(tooltip).toHaveTextContent('Pinball Book');
		expect(tooltip).toHaveTextContent('Jane Doe, 1992');
		expect(tooltip).toHaveTextContent('p. 42');

		await fireEvent.mouseLeave(getCitation('1'));
		await vi.advanceTimersByTimeAsync(99);
		expect(screen.getByRole('tooltip')).toBeInTheDocument();

		await vi.advanceTimersByTimeAsync(1);
		expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
	});

	it('shows on focus and closes on escape', async () => {
		renderTooltip('<p>Focus <sup data-cite-id="1" tabindex="0">[1]</sup>.</p>');
		await vi.waitFor(() => expect(GET).toHaveBeenCalledTimes(1));

		const citation = getCitation('1');
		await fireEvent.focus(citation);
		expect(await screen.findByRole('tooltip')).toHaveTextContent('Pinball Book');

		await fireEvent.keyDown(citation, { key: 'Escape' });
		expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
	});

	it('pins on click, unpins on second click, and dismisses on outside click', async () => {
		renderTooltip('<p>Click <sup data-cite-id="1" tabindex="0">[1]</sup>.</p>');
		await vi.waitFor(() => expect(GET).toHaveBeenCalledTimes(1));

		const citation = getCitation('1');
		await fireEvent.click(citation);
		expect(await screen.findByRole('tooltip')).toHaveTextContent('Pinball Book');

		await fireEvent.click(document.body);
		expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

		await fireEvent.click(citation);
		expect(await screen.findByRole('tooltip')).toBeInTheDocument();

		await fireEvent.click(citation);
		expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
	});

	it('repositions on resize and scroll while visible', async () => {
		renderTooltip('<p>Move <sup data-cite-id="1" tabindex="0">[1]</sup>.</p>');
		await vi.waitFor(() => expect(GET).toHaveBeenCalledTimes(1));

		await fireEvent.mouseEnter(getCitation('1'));
		const tooltip = (await screen.findByRole('tooltip')) as HTMLDivElement;

		await vi.waitFor(() => {
			expect(tooltip.style.left).toBe('22px');
			expect(tooltip.style.top).toBe('74px');
		});

		anchorRect = rect({ left: 220, top: 260, width: 24, height: 16 });
		await fireEvent(window, new Event('resize'));
		await vi.waitFor(() => {
			expect(tooltip.style.left).toBe('142px');
			expect(tooltip.style.top).toBe('174px');
		});

		anchorRect = rect({ left: 260, top: 280, width: 24, height: 16 });
		await fireEvent(window, new Event('scroll'));
		await vi.waitFor(() => {
			expect(tooltip.style.left).toBe('182px');
			expect(tooltip.style.top).toBe('194px');
		});
	});

	describe('citations prop (no-fetch)', () => {
		const propCitations: InlineCitation[] = [
			{
				id: 1,
				index: 1,
				source_name: 'Prop Book',
				source_type: 'book',
				author: 'Prop Author',
				year: 2020,
				locator: 'ch. 1',
				links: []
			}
		];

		it('uses prop data and does not fetch', async () => {
			renderTooltip('<p>Cited <sup data-cite-id="1" tabindex="0">[1]</sup>.</p>', propCitations);
			// Give it time to potentially fetch
			await vi.advanceTimersByTimeAsync(100);
			expect(GET).not.toHaveBeenCalled();

			// Tooltip should still work from prop data
			await fireEvent.mouseEnter(getCitation('1'));
			const tooltip = await screen.findByRole('tooltip');
			expect(tooltip).toHaveTextContent('Prop Book');
			expect(tooltip).toHaveTextContent('Prop Author, 2020');
		});
	});

	describe('fallback fetch (no citations prop)', () => {
		it('fetches from batch endpoint when no citations prop', async () => {
			renderTooltip('<p>Cited <sup data-cite-id="1" tabindex="0">[1]</sup>.</p>');
			await vi.waitFor(() => {
				expect(GET).toHaveBeenCalledWith('/api/citation-instances/batch/', {
					params: { query: { ids: '1' } }
				});
			});
		});
	});
});
