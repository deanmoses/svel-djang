import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MediaUploadZone from './MediaUploadZone.svelte';

const { uploadMedia } = vi.hoisted(() => ({
  uploadMedia: vi.fn(),
}));

vi.mock('$lib/api/media-api', () => ({
  IMAGE_ACCEPT: 'image/*',
  MAX_FILE_SIZE_BYTES: 20 * 1024 * 1024,
  uploadMedia,
}));

function makeFileList(files: File[]): FileList {
  return {
    ...Object.fromEntries(files.entries()),
    length: files.length,
    item(index: number) {
      return files[index] ?? null;
    },
    [Symbol.iterator]() {
      return files[Symbol.iterator]();
    },
  } as FileList;
}

function setInputFiles(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, 'files', {
    configurable: true,
    value: makeFileList(files),
  });
}

function renderZone() {
  const onuploaded = vi.fn();
  const result = render(MediaUploadZone, {
    entityType: 'model',
    slug: 'attack-from-mars',
    onuploaded,
  });
  return { ...result, onuploaded };
}

beforeEach(() => {
  uploadMedia.mockReset().mockResolvedValue({
    asset_uuid: 'uploaded-1',
    renditions: { thumb: 'thumb', display: 'display' },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('MediaUploadZone', () => {
  it('shows a category prompt and no select button until a category is picked', async () => {
    const user = userEvent.setup();
    renderZone();

    expect(screen.getByText(/choose category to upload images/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /select images/i })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByRole('combobox'), 'backglass');
    expect(screen.getByRole('button', { name: /select images/i })).not.toBeDisabled();
  });

  it('opens the hidden file input from the select-images button after picking a category', async () => {
    const user = userEvent.setup();
    const { container } = renderZone();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const clickSpy = vi.spyOn(input, 'click');

    await user.selectOptions(screen.getByRole('combobox'), 'backglass');
    await user.click(screen.getByRole('button', { name: /select images/i }));

    expect(clickSpy).toHaveBeenCalledOnce();
  });

  it('uploads selected files and calls onuploaded with new uuids on success', async () => {
    const user = userEvent.setup();
    const { container, onuploaded } = renderZone();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['image'], 'cabinet.png', { type: 'image/png' });

    await user.selectOptions(screen.getByRole('combobox'), 'backglass');
    setInputFiles(input, [file]);

    await fireEvent.change(input);

    await vi.waitFor(() => {
      expect(uploadMedia).toHaveBeenCalledWith(
        file,
        'model',
        'attack-from-mars',
        { category: 'backglass' },
        expect.any(Function),
      );
    });
    await vi.waitFor(() => {
      expect(onuploaded).toHaveBeenCalledWith(['uploaded-1'], 'backglass');
    });
    expect(screen.queryByText('Upload results')).not.toBeInTheDocument();
  });

  it('toggles dragging state on drag events when a category is selected', async () => {
    const user = userEvent.setup();
    renderZone();
    await user.selectOptions(screen.getByRole('combobox'), 'backglass');

    const dropZone = screen
      .getByText('Drag and drop images here')
      .closest('.drop-zone') as HTMLElement;

    await fireEvent.dragEnter(dropZone);
    expect(dropZone).toHaveClass('dragging');

    await fireEvent.dragLeave(dropZone);
    expect(dropZone).not.toHaveClass('dragging');
  });

  it('shows upload errors and stays in failure state', async () => {
    uploadMedia.mockRejectedValueOnce(new Error('Upload exploded'));
    const user = userEvent.setup();
    const { container, onuploaded } = renderZone();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['image'], 'backglass.png', { type: 'image/png' });

    await user.selectOptions(screen.getByRole('combobox'), 'backglass');
    setInputFiles(input, [file]);

    await fireEvent.change(input);

    expect(await screen.findByText('Upload exploded')).toBeInTheDocument();
    expect(onuploaded).not.toHaveBeenCalled();
    expect(screen.getByText('Upload results')).toBeInTheDocument();
  });
});
