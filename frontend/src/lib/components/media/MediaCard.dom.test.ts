import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MediaCard from './MediaCard.svelte';
import { makeMedia } from './media-test-fixtures';

function renderCard(
  props: Partial<{
    canEdit: boolean;
    categories: string[];
    onclick: (assetUuid: string) => void;
    ondelete: (assetUuid: string) => void;
    onsetprimary: (assetUuid: string) => void;
    oncategorychange: (assetUuid: string, category: string) => void;
  }> = {},
) {
  return render(MediaCard, {
    asset: makeMedia(1, { category: 'backglass', is_primary: false }),
    canEdit: true,
    onclick: vi.fn(),
    ondelete: vi.fn(),
    onsetprimary: vi.fn(),
    ...props,
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('MediaCard', () => {
  it('opens the media when clicked or activated by keyboard', async () => {
    const user = userEvent.setup();
    const onclick = vi.fn();
    renderCard({ onclick, canEdit: false });

    const card = screen.getByRole('button', { name: /open backglass image/i });
    await user.click(card);
    await user.keyboard('{Enter}');
    await user.keyboard(' ');

    expect(onclick).toHaveBeenCalledTimes(3);
    expect(onclick).toHaveBeenCalledWith('asset-1');
  });

  it('routes the make-primary action without opening the card', async () => {
    const user = userEvent.setup();
    const onclick = vi.fn();
    const onsetprimary = vi.fn();
    renderCard({ onclick, onsetprimary });

    await user.click(screen.getByRole('button', { name: /make primary/i }));

    expect(onsetprimary).toHaveBeenCalledWith('asset-1');
    expect(onclick).not.toHaveBeenCalled();
  });

  it('confirms deletion before calling ondelete and keeps the card closed', async () => {
    const user = userEvent.setup();
    const onclick = vi.fn();
    const ondelete = vi.fn();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderCard({ onclick, ondelete });

    await user.click(screen.getByRole('button', { name: /remove/i }));

    expect(confirmSpy).toHaveBeenCalledWith('Remove this image from this machine?');
    expect(ondelete).toHaveBeenCalledWith('asset-1');
    expect(onclick).not.toHaveBeenCalled();
  });

  describe('category pill', () => {
    const categories = ['playfield', 'backglass', 'cabinet'];

    it('renders the static badge when no categories are provided', () => {
      renderCard();
      expect(screen.queryByRole('button', { name: /image category/i })).not.toBeInTheDocument();
      // Visible category text still appears (as the static badge).
      expect(screen.getByText('backglass')).toBeInTheDocument();
    });

    it('replaces the static badge with a PillSelect when categories are provided', () => {
      renderCard({ categories });
      expect(screen.getByRole('button', { name: 'Image category: backglass' })).toBeInTheDocument();
    });

    it('fires oncategorychange with (assetUuid, category) when a different option is picked', async () => {
      const user = userEvent.setup();
      const onclick = vi.fn();
      const oncategorychange = vi.fn();
      renderCard({ categories, onclick, oncategorychange });

      await user.click(screen.getByRole('button', { name: 'Image category: backglass' }));
      await user.click(screen.getByRole('option', { name: 'playfield' }));

      expect(oncategorychange).toHaveBeenCalledWith('asset-1', 'playfield');
      expect(onclick).not.toHaveBeenCalled();
    });

    it('clicking the pill does NOT open the lightbox', async () => {
      const user = userEvent.setup();
      const onclick = vi.fn();
      renderCard({ categories, onclick });

      await user.click(screen.getByRole('button', { name: 'Image category: backglass' }));

      expect(screen.getByRole('listbox')).toBeInTheDocument();
      expect(onclick).not.toHaveBeenCalled();
    });

    it('Enter on the pill opens the listbox without firing the card onclick', async () => {
      const user = userEvent.setup();
      const onclick = vi.fn();
      renderCard({ categories, onclick });

      const trigger = screen.getByRole('button', { name: 'Image category: backglass' });
      trigger.focus();
      await user.keyboard('{Enter}');

      expect(screen.getByRole('listbox')).toBeInTheDocument();
      expect(onclick).not.toHaveBeenCalled();
    });

    it('Space on the pill opens the listbox without firing the card onclick', async () => {
      const user = userEvent.setup();
      const onclick = vi.fn();
      renderCard({ categories, onclick });

      const trigger = screen.getByRole('button', { name: 'Image category: backglass' });
      trigger.focus();
      await user.keyboard(' ');

      expect(screen.getByRole('listbox')).toBeInTheDocument();
      expect(onclick).not.toHaveBeenCalled();
    });

    it('falls back to the static badge when canEdit is false even if categories are provided', () => {
      renderCard({ categories, canEdit: false });
      expect(screen.queryByRole('button', { name: /image category/i })).not.toBeInTheDocument();
      expect(screen.getByText('backglass')).toBeInTheDocument();
    });
  });
});
