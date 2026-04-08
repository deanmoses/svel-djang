import { render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MediaCard from './MediaCard.svelte';
import { makeMedia } from './media-test-fixtures';

function renderCard(
	props: Partial<{
		canEdit: boolean;
		onclick: (assetUuid: string) => void;
		ondelete: (assetUuid: string) => void;
		onsetprimary: (assetUuid: string) => void;
	}> = {}
) {
	return render(MediaCard, {
		asset: makeMedia(1, { category: 'Backglass', is_primary: false }),
		canEdit: true,
		onclick: vi.fn(),
		ondelete: vi.fn(),
		onsetprimary: vi.fn(),
		...props
	});
}

afterEach(() => {
	vi.restoreAllMocks();
});

describe('MediaCard', () => {
	it('opens the media when clicked or activated by keyboard', async () => {
		const user = userEvent.setup();
		const onclick = vi.fn();
		const { container } = renderCard({ onclick, canEdit: false });

		const card = container.querySelector('.media-card') as HTMLElement;
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

		await user.click(document.querySelector('.action-btn') as HTMLElement);

		expect(onsetprimary).toHaveBeenCalledWith('asset-1');
		expect(onclick).not.toHaveBeenCalled();
	});

	it('confirms deletion before calling ondelete and keeps the card closed', async () => {
		const user = userEvent.setup();
		const onclick = vi.fn();
		const ondelete = vi.fn();
		vi.spyOn(window, 'confirm').mockReturnValue(true);
		renderCard({ onclick, ondelete });

		await user.click(document.querySelector('.action-btn--danger') as HTMLElement);

		expect(window.confirm).toHaveBeenCalledWith('Remove this image from this machine?');
		expect(ondelete).toHaveBeenCalledWith('asset-1');
		expect(onclick).not.toHaveBeenCalled();
	});
});
