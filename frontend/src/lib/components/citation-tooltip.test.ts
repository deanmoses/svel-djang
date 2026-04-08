import { describe, it, expect } from 'vitest';
import { computePosition, reduceTooltip } from './citation-tooltip';
import type { TooltipState } from './citation-tooltip';

// ── computePosition ────���────────────────────────────────────────

describe('computePosition', () => {
	const anchor = (top: number, left: number, width: number, height: number) =>
		({ top, left, width, height, bottom: top + height, right: left + width }) as DOMRect;

	it('positions above the anchor by default', () => {
		const pos = computePosition(anchor(200, 100, 20, 16), 160, 80, 1024, 768);
		expect(pos.above).toBe(true);
		// Should be above: y = anchorTop - tooltipHeight - gap
		expect(pos.y).toBeLessThan(200);
	});

	it('centers horizontally on the anchor', () => {
		const pos = computePosition(anchor(200, 500, 20, 16), 160, 80, 1024, 768);
		// Center of anchor = 500 + 10 = 510. Tooltip left = 510 - 80 = 430.
		expect(pos.x).toBe(430);
	});

	it('flips below when near the top of viewport', () => {
		const pos = computePosition(anchor(20, 100, 20, 16), 160, 80, 1024, 768);
		expect(pos.above).toBe(false);
		// Should be below: y = anchorBottom + gap
		expect(pos.y).toBeGreaterThan(36);
	});

	it('clamps to left edge', () => {
		const pos = computePosition(anchor(200, 0, 20, 16), 160, 80, 1024, 768);
		expect(pos.x).toBeGreaterThanOrEqual(8);
	});

	it('clamps to right edge', () => {
		const pos = computePosition(anchor(200, 1010, 20, 16), 160, 80, 1024, 768);
		expect(pos.x).toBeLessThanOrEqual(1024 - 160 - 8);
	});
});

// ── reduceTooltip ───────────────────────────────────────���───────

describe('reduceTooltip', () => {
	const initial: TooltipState = { activeId: null, pinned: false };
	const showing = (id: number): TooltipState => ({ activeId: id, pinned: false });
	const pinned = (id: number): TooltipState => ({ activeId: id, pinned: true });

	describe('mouseenter', () => {
		it('shows tooltip for the citation', () => {
			const result = reduceTooltip(initial, { type: 'mouseenter', id: 1 });
			expect(result.activeId).toBe(1);
			expect(result.pinned).toBe(false);
			expect(result.cancelHide).toBe(true);
		});

		it('switches to new citation when not pinned', () => {
			const result = reduceTooltip(showing(1), { type: 'mouseenter', id: 2 });
			expect(result.activeId).toBe(2);
			expect(result.pinned).toBe(false);
		});

		it('does not switch when pinned on a different citation', () => {
			const result = reduceTooltip(pinned(1), { type: 'mouseenter', id: 2 });
			expect(result.activeId).toBe(1);
			expect(result.pinned).toBe(true);
		});
	});

	describe('mouseleave', () => {
		it('schedules hide when not pinned', () => {
			const result = reduceTooltip(showing(1), { type: 'mouseleave', id: 1 });
			expect(result.scheduleHide).toBe(true);
		});

		it('does not schedule hide when pinned', () => {
			const result = reduceTooltip(pinned(1), { type: 'mouseleave', id: 1 });
			expect(result.scheduleHide).toBeUndefined();
		});
	});

	describe('click', () => {
		it('pins the tooltip when not pinned', () => {
			const result = reduceTooltip(showing(1), { type: 'click', id: 1 });
			expect(result.activeId).toBe(1);
			expect(result.pinned).toBe(true);
		});

		it('unpins and hides when clicking the same pinned citation', () => {
			const result = reduceTooltip(pinned(1), { type: 'click', id: 1 });
			expect(result.activeId).toBeNull();
			expect(result.pinned).toBe(false);
		});

		it('switches pin to a different citation', () => {
			const result = reduceTooltip(pinned(1), { type: 'click', id: 2 });
			expect(result.activeId).toBe(2);
			expect(result.pinned).toBe(true);
		});

		it('pins from initial state (mobile tap)', () => {
			const result = reduceTooltip(initial, { type: 'click', id: 1 });
			expect(result.activeId).toBe(1);
			expect(result.pinned).toBe(true);
		});
	});

	describe('focus', () => {
		it('shows tooltip on keyboard focus', () => {
			const result = reduceTooltip(initial, { type: 'focus', id: 1 });
			expect(result.activeId).toBe(1);
			expect(result.pinned).toBe(false);
			expect(result.cancelHide).toBe(true);
		});

		it('does not switch when pinned on a different citation', () => {
			const result = reduceTooltip(pinned(1), { type: 'focus', id: 2 });
			expect(result.activeId).toBe(1);
			expect(result.pinned).toBe(true);
		});
	});

	describe('blur', () => {
		it('schedules hide when not pinned', () => {
			const result = reduceTooltip(showing(1), { type: 'blur', id: 1 });
			expect(result.scheduleHide).toBe(true);
		});

		it('does not schedule hide when pinned', () => {
			const result = reduceTooltip(pinned(1), { type: 'blur', id: 1 });
			expect(result.scheduleHide).toBeUndefined();
		});
	});

	describe('escape', () => {
		it('hides and unpins', () => {
			const result = reduceTooltip(pinned(1), { type: 'escape' });
			expect(result.activeId).toBeNull();
			expect(result.pinned).toBe(false);
		});

		it('hides when showing but not pinned', () => {
			const result = reduceTooltip(showing(1), { type: 'escape' });
			expect(result.activeId).toBeNull();
		});

		it('is a no-op when already hidden', () => {
			const result = reduceTooltip(initial, { type: 'escape' });
			expect(result.activeId).toBeNull();
			expect(result.pinned).toBe(false);
		});
	});

	describe('click-outside', () => {
		it('hides and unpins when pinned', () => {
			const result = reduceTooltip(pinned(1), { type: 'click-outside' });
			expect(result.activeId).toBeNull();
			expect(result.pinned).toBe(false);
		});

		it('is a no-op when not pinned', () => {
			const result = reduceTooltip(showing(1), { type: 'click-outside' });
			expect(result.activeId).toBe(1);
			expect(result.pinned).toBe(false);
		});
	});

	describe('navigate', () => {
		it('dismisses tooltip and signals navigation', () => {
			const result = reduceTooltip(showing(1), { type: 'navigate', id: 1 });
			expect(result.activeId).toBeNull();
			expect(result.pinned).toBe(false);
			expect(result.navigate).toBe(true);
		});

		it('dismisses pinned tooltip', () => {
			const result = reduceTooltip(pinned(1), { type: 'navigate', id: 1 });
			expect(result.activeId).toBeNull();
			expect(result.pinned).toBe(false);
			expect(result.navigate).toBe(true);
		});

		it('works from initial state', () => {
			const result = reduceTooltip(initial, { type: 'navigate', id: 1 });
			expect(result.activeId).toBeNull();
			expect(result.pinned).toBe(false);
			expect(result.navigate).toBe(true);
		});
	});

	describe('tooltip-mouseenter', () => {
		it('cancels pending hide', () => {
			const result = reduceTooltip(showing(1), { type: 'tooltip-mouseenter' });
			expect(result.cancelHide).toBe(true);
			expect(result.activeId).toBe(1);
		});
	});

	describe('tooltip-mouseleave', () => {
		it('schedules hide when not pinned', () => {
			const result = reduceTooltip(showing(1), { type: 'tooltip-mouseleave' });
			expect(result.scheduleHide).toBe(true);
		});

		it('does not schedule hide when pinned', () => {
			const result = reduceTooltip(pinned(1), { type: 'tooltip-mouseleave' });
			expect(result.scheduleHide).toBeUndefined();
		});
	});
});
