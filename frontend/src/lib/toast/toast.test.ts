import { afterEach, describe, expect, it } from 'vitest';

import { toast } from './toast.svelte';

afterEach(() => {
	toast._resetForTest();
});

describe('toast store', () => {
	it('pushes messages and returns a handle with a unique id', () => {
		const a = toast.success('Saved one.');
		const b = toast.info('Heads up.');
		expect(a.id).not.toBe(b.id);
		expect(toast.messages.map((m) => m.text)).toEqual(['Saved one.', 'Heads up.']);
	});

	it('caps the visible queue at three', () => {
		for (let i = 0; i < 5; i += 1) {
			toast.info(`msg ${i}`);
		}
		expect(toast.messages).toHaveLength(3);
		// FIFO drop — earliest messages were evicted.
		expect(toast.messages.map((m) => m.text)).toEqual(['msg 2', 'msg 3', 'msg 4']);
	});

	it('update() replaces text but keeps the same id and slot', () => {
		const handle = toast.success('Deleted X.');
		const originalId = handle.id;
		handle.update('Restored X.');
		expect(toast.messages).toHaveLength(1);
		expect(toast.messages[0].id).toBe(originalId);
		expect(toast.messages[0].text).toBe('Restored X.');
	});

	it('update() after dismiss is a no-op', () => {
		const handle = toast.info('here');
		handle.dismiss();
		handle.update('should not reappear');
		expect(toast.messages).toHaveLength(0);
	});

	it('errors default to Infinity dwell (manual dismiss only)', () => {
		toast.error('broken');
		expect(toast.messages[0].dwellMs).toBe(Infinity);
	});

	it('persistUntilNav survives one navigation, clears on the next', () => {
		toast.success('Deleted X.', { persistUntilNav: true });
		toast.info('transient', {});
		// First navigation: persistent toast survives; transient stays too
		// (it has no nav-persistence rule but isn't auto-cleared here either).
		toast.onNavigation();
		expect(toast.messages.map((m) => m.text)).toContain('Deleted X.');
		// Second navigation: the persistent toast now clears.
		toast.onNavigation();
		expect(toast.messages.map((m) => m.text)).not.toContain('Deleted X.');
	});

	it('update() on a persistUntilNav toast resets its nav counter', () => {
		const handle = toast.success('Deleted X.', { persistUntilNav: true });
		toast.onNavigation();
		handle.update('Restored X.');
		// The user has just acted — the toast should survive the next nav.
		toast.onNavigation();
		expect(toast.messages.map((m) => m.text)).toContain('Restored X.');
	});
});
