/**
 * Pure logic for the citation tooltip: types, positioning, and interaction
 * state machine. Extracted so it's unit-testable without DOM or component
 * lifecycle.
 */

// ── Types ───────────────────────────────────────────────────────

/** Citation data for tooltip display. Shared by both the batch endpoint
 *  and the page API — the tooltip only needs these fields. */
export interface CitationInfo {
	id: number;
	source_name: string;
	source_type: string;
	author: string;
	year?: number | null;
	locator: string;
	links: Array<{ url: string; label: string }>;
}

/** Citation data from the page API, which includes the display index
 *  (position in the rendered text). Used for the references section
 *  and scroll navigation. */
export interface InlineCitation extends CitationInfo {
	index: number;
}

// ── Positioning ─────────────────────────────────────────────────

export interface TooltipPosition {
	x: number;
	y: number;
	above: boolean;
}

const DEFAULT_GAP = 6;
const EDGE_PADDING = 8;

export function computePosition(
	anchorRect: DOMRect,
	tooltipWidth: number,
	tooltipHeight: number,
	viewportWidth: number,
	_viewportHeight: number,
	gap: number = DEFAULT_GAP
): TooltipPosition {
	const anchorCenterX = anchorRect.left + anchorRect.width / 2;
	let x = anchorCenterX - tooltipWidth / 2;

	// Clamp horizontal
	x = Math.max(EDGE_PADDING, Math.min(x, viewportWidth - tooltipWidth - EDGE_PADDING));

	// Default above; flip below if not enough room
	const above = anchorRect.top - tooltipHeight - gap >= 0;
	const y = above ? anchorRect.top - tooltipHeight - gap : anchorRect.bottom + gap;

	return { x, y, above };
}

// ── Interaction state machine ───────────────────────────────────

export type TooltipAction =
	| { type: 'mouseenter'; id: number }
	| { type: 'mouseleave'; id: number }
	| { type: 'click'; id: number }
	| { type: 'navigate'; id: number }
	| { type: 'focus'; id: number }
	| { type: 'blur'; id: number }
	| { type: 'escape' }
	| { type: 'click-outside' }
	| { type: 'tooltip-mouseenter' }
	| { type: 'tooltip-mouseleave' };

export type TooltipState = {
	activeId: number | null;
	pinned: boolean;
};

export type TooltipEffect = {
	scheduleHide?: boolean;
	cancelHide?: boolean;
	navigate?: boolean;
};

export function reduceTooltip(
	state: TooltipState,
	action: TooltipAction
): TooltipState & TooltipEffect {
	switch (action.type) {
		case 'mouseenter':
		case 'focus':
			if (state.pinned && state.activeId !== action.id) {
				return { ...state };
			}
			return { activeId: action.id, pinned: false, cancelHide: true };

		case 'mouseleave':
		case 'blur':
			if (state.pinned) {
				return { ...state };
			}
			return { ...state, scheduleHide: true };

		case 'click':
			if (state.pinned && state.activeId === action.id) {
				return { activeId: null, pinned: false };
			}
			return { activeId: action.id, pinned: true, cancelHide: true };

		case 'navigate':
			return { activeId: null, pinned: false, navigate: true };

		case 'escape':
			return { activeId: null, pinned: false };

		case 'click-outside':
			if (state.pinned) {
				return { activeId: null, pinned: false };
			}
			return { ...state };

		case 'tooltip-mouseenter':
			return { ...state, cancelHide: true };

		case 'tooltip-mouseleave':
			if (state.pinned) {
				return { ...state };
			}
			return { ...state, scheduleHide: true };
	}
}
