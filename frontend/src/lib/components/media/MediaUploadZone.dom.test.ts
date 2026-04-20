import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MediaUploadZone from './MediaUploadZone.svelte';

const { uploadMedia } = vi.hoisted(() => ({
	uploadMedia: vi.fn()
}));

vi.mock('$lib/api/media-api', () => ({
	IMAGE_ACCEPT: 'image/*',
	MAX_FILE_SIZE_BYTES: 20 * 1024 * 1024,
	uploadMedia
}));

function makeFileList(files: File[]): FileList {
	return {
		...files,
		length: files.length,
		item(index: number) {
			return files[index] ?? null;
		},
		[Symbol.iterator]() {
			return files[Symbol.iterator]();
		}
	} as FileList;
}

function setInputFiles(input: HTMLInputElement, files: File[]) {
	Object.defineProperty(input, 'files', {
		configurable: true,
		value: makeFileList(files)
	});
}

function renderZone() {
	const onuploaded = vi.fn();
	const result = render(MediaUploadZone, {
		entityType: 'model',
		slug: 'attack-from-mars',
		onuploaded
	});
	return { ...result, onuploaded };
}

beforeEach(() => {
	uploadMedia.mockReset().mockResolvedValue({
		asset_uuid: 'uploaded-1',
		renditions: { thumb: 'thumb', display: 'display' }
	});
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe('MediaUploadZone', () => {
	it('opens the hidden file input from the choose-files button', async () => {
		const user = userEvent.setup();
		const { container } = renderZone();
		const input = container.querySelector('input[type="file"]') as HTMLInputElement;
		const clickSpy = vi.spyOn(input, 'click');

		await user.click(screen.getByRole('button', { name: /choose files/i }));

		expect(clickSpy).toHaveBeenCalledTimes(1);
	});

	it('uploads selected files and calls onuploaded on success', async () => {
		const user = userEvent.setup();
		const { container, onuploaded } = renderZone();
		const input = container.querySelector('input[type="file"]') as HTMLInputElement;
		const file = new File(['image'], 'cabinet.png', { type: 'image/png' });

		await user.selectOptions(screen.getByRole('combobox'), 'backglass');
		await user.click(screen.getByRole('checkbox', { name: /set as primary/i }));
		setInputFiles(input, [file]);

		await fireEvent.change(input);

		await vi.waitFor(() => {
			expect(uploadMedia).toHaveBeenCalledWith(
				file,
				'model',
				'attack-from-mars',
				{ category: 'backglass', isPrimary: true },
				expect.any(Function)
			);
		});
		await vi.waitFor(() => {
			expect(onuploaded).toHaveBeenCalledTimes(1);
		});
		expect(screen.queryByText('Upload results')).not.toBeInTheDocument();
	});

	it('toggles dragging state on drag events', async () => {
		renderZone();
		const dropZone = screen
			.getByText('Drag and drop images here')
			.closest('.drop-zone') as HTMLElement;

		await fireEvent.dragEnter(dropZone);
		expect(dropZone).toHaveClass('dragging');

		await fireEvent.dragLeave(dropZone);
		expect(dropZone).not.toHaveClass('dragging');
	});

	it('shows upload errors and does not auto-open uploads on failure', async () => {
		uploadMedia.mockRejectedValueOnce(new Error('Upload exploded'));
		const { container, onuploaded } = renderZone();
		const input = container.querySelector('input[type="file"]') as HTMLInputElement;
		const file = new File(['image'], 'backglass.png', { type: 'image/png' });
		setInputFiles(input, [file]);

		await fireEvent.change(input);

		expect(await screen.findByText('Upload exploded')).toBeInTheDocument();
		expect(onuploaded).not.toHaveBeenCalled();
		expect(screen.getByRole('button', { name: /view uploads/i })).toBeInTheDocument();
	});
});
