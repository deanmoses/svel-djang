import { render } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import KioskMode from './KioskMode.svelte';
import { clearKioskCookies, setKioskCookies } from './config';

const { goto, mockPage } = vi.hoisted(() => ({
  goto: vi.fn(),
  mockPage: { url: new URL('http://localhost/kiosk') },
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$app/state', () => ({ page: mockPage }));

describe('KioskMode', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearKioskCookies();
    goto.mockClear();
    mockPage.url = new URL('http://localhost/kiosk');
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('navigates to /kiosk after the cookie-supplied idle timeout', () => {
    setKioskCookies(1, 5);

    render(KioskMode);

    vi.advanceTimersByTime(5000);
    expect(goto).toHaveBeenCalledWith('/kiosk', { invalidateAll: true, replaceState: true });
  });

  it('does not arm the timer on /kiosk/edit/[id] (staff editor)', () => {
    setKioskCookies(1, 5);
    mockPage.url = new URL('http://localhost/kiosk/edit/3');

    render(KioskMode);

    vi.advanceTimersByTime(60_000);
    expect(goto).not.toHaveBeenCalled();
  });

  it('does not arm the timer on /kiosk/edit (list page)', () => {
    setKioskCookies(1, 5);
    mockPage.url = new URL('http://localhost/kiosk/edit');

    render(KioskMode);

    vi.advanceTimersByTime(60_000);
    expect(goto).not.toHaveBeenCalled();
  });

  it('arms the timer on unrelated routes — global idle return is the point', () => {
    setKioskCookies(1, 5);
    mockPage.url = new URL('http://localhost/titles/gorgar');

    render(KioskMode);

    vi.advanceTimersByTime(5000);
    expect(goto).toHaveBeenCalledWith('/kiosk', { invalidateAll: true, replaceState: true });
  });

  it('resets the timer when the user interacts', () => {
    setKioskCookies(1, 5);

    render(KioskMode);

    vi.advanceTimersByTime(4000);
    window.dispatchEvent(new Event('pointerdown'));
    vi.advanceTimersByTime(4000);
    expect(goto).not.toHaveBeenCalled();

    vi.advanceTimersByTime(2000);
    expect(goto).toHaveBeenCalledOnce();
  });

  it('falls back to the default idle timeout when no cookie is set', () => {
    render(KioskMode);

    vi.advanceTimersByTime(180 * 1000 - 1);
    expect(goto).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(goto).toHaveBeenCalledOnce();
  });

  it('cleans up timer and listeners on unmount', () => {
    setKioskCookies(1, 5);

    const { unmount } = render(KioskMode);
    unmount();

    vi.advanceTimersByTime(10_000);
    expect(goto).not.toHaveBeenCalled();
  });
});
