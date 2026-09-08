import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MediaLightbox from './MediaLightbox.svelte';
import { MEDIA_ITEMS } from './media-test-fixtures';

function renderLightbox(initialIndex = 0) {
  const onclose = vi.fn();
  const result = render(MediaLightbox, {
    media: MEDIA_ITEMS.slice(0, 2),
    initialIndex,
    onclose,
  });
  return { ...result, onclose };
}

describe('MediaLightbox', () => {
  afterEach(() => {
    document.body.style.overflow = '';
  });

  it('locks body scroll while mounted and restores it on unmount', () => {
    const { unmount } = renderLightbox();

    expect(document.body.style.overflow).toBe('hidden');

    unmount();
    expect(document.body.style.overflow).toBe('');
  });

  it('exposes dialog semantics and closes on Escape and backdrop dismiss', async () => {
    const user = userEvent.setup();
    const { container, onclose } = renderLightbox();

    expect(screen.getByRole('dialog', { name: /media viewer/i })).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(onclose).toHaveBeenCalledOnce();

    const backdrop = container.querySelector('.backdrop-dismiss');
    expect(backdrop).toBeInTheDocument();
    await user.click(backdrop as Element);
    expect(onclose).toHaveBeenCalledTimes(2);
  });

  it('navigates with arrow keys and updates edge button visibility', async () => {
    renderLightbox();

    expect(screen.getByText('1 / 2')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /previous/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();

    await fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument();

    await fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(screen.getByText('1 / 2')).toBeInTheDocument();
  });

  it('traps focus within the lightbox when tabbing forward and backward', async () => {
    const user = userEvent.setup();
    renderLightbox();

    const closeBtn = screen.getByRole('button', { name: /close/i });
    await vi.waitFor(() => {
      expect(closeBtn).toHaveFocus();
    });

    // Forward through all focusables, then wrap back to close.
    const next = screen.getByRole('button', { name: /next/i });
    const uploaderLink = screen.getByRole('link');

    await user.keyboard('{Tab}');
    expect(next).toHaveFocus();

    await user.keyboard('{Tab}');
    expect(uploaderLink).toHaveFocus();

    // From last focusable, Tab wraps back to close.
    await user.keyboard('{Tab}');
    expect(closeBtn).toHaveFocus();

    // Shift+Tab from first wraps to last.
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(uploaderLink).toHaveFocus();
  });
});
