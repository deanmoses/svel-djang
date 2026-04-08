import { describe, expect, it, vi, beforeEach } from 'vitest';

import { createUploadManager } from './media-upload.svelte';
import { MAX_FILE_SIZE_BYTES } from './api/media-api';

// Mock the uploadMedia function
vi.mock('./api/media-api', async (importOriginal) => {
	const actual = (await importOriginal()) as Record<string, unknown>;
	return {
		...actual,
		uploadMedia: vi.fn()
	};
});

import { uploadMedia } from './api/media-api';
const mockUpload = vi.mocked(uploadMedia);

function makeFile(name: string, size: number = 1024, type: string = 'image/jpeg'): File {
	const data = new Uint8Array(size);
	return new File([data], name, { type });
}

function makeFileList(...files: File[]): FileList {
	const list = {
		length: files.length,
		item: (i: number) => files[i] ?? null,
		[Symbol.iterator]: function* () {
			for (const f of files) yield f;
		}
	} as unknown as FileList;
	for (let i = 0; i < files.length; i++) {
		Object.defineProperty(list, i, { value: files[i] });
	}
	return list;
}

const UPLOAD_RESULT = {
	asset_uuid: 'abc-123',
	kind: 'image',
	status: 'ready',
	original_filename: 'test.jpg',
	width: 800,
	height: 600,
	renditions: {
		original: '/media/abc/original',
		thumb: '/media/abc/thumb',
		display: '/media/abc/display'
	},
	attachment: {
		entity_type: 'model',
		slug: 'test',
		category: 'backglass',
		is_primary: false
	}
};

describe('createUploadManager', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('starts in idle state with empty file list', () => {
		const mgr = createUploadManager();
		expect(mgr.files).toEqual([]);
		expect(mgr.isUploading).toBe(false);
	});

	// --- File validation ---

	it('rejects oversized files', async () => {
		const mgr = createUploadManager();
		const bigFile = makeFile('huge.jpg', MAX_FILE_SIZE_BYTES + 1);

		await mgr.upload(makeFileList(bigFile), 'model', 'test');

		expect(mgr.files).toHaveLength(1);
		expect(mgr.files[0].status).toBe('error');
		expect(mgr.files[0].error).toMatch(/size/i);
		expect(mockUpload).not.toHaveBeenCalled();
	});

	// --- Successful upload ---

	it('transitions to success on successful upload', async () => {
		const mgr = createUploadManager();
		mockUpload.mockResolvedValueOnce(UPLOAD_RESULT);

		await mgr.upload(makeFileList(makeFile('photo.jpg')), 'model', 'test');

		expect(mgr.files).toHaveLength(1);
		expect(mgr.files[0].status).toBe('success');
		expect(mgr.files[0].progress).toBe(100);
		expect(mgr.isUploading).toBe(false);
	});

	// --- Failed upload ---

	it('transitions to error on upload failure', async () => {
		const mgr = createUploadManager();
		mockUpload.mockRejectedValueOnce(new Error('Server error'));

		await mgr.upload(makeFileList(makeFile('photo.jpg')), 'model', 'test');

		expect(mgr.files).toHaveLength(1);
		expect(mgr.files[0].status).toBe('error');
		expect(mgr.files[0].error).toBe('Server error');
		expect(mgr.isUploading).toBe(false);
	});

	// --- Multi-file: partial failure ---

	it('handles partial failure independently per file', async () => {
		const mgr = createUploadManager();
		mockUpload.mockResolvedValueOnce(UPLOAD_RESULT);
		mockUpload.mockRejectedValueOnce(new Error('Rate limited'));

		await mgr.upload(makeFileList(makeFile('a.jpg'), makeFile('b.jpg')), 'model', 'test');

		expect(mgr.files).toHaveLength(2);
		expect(mgr.files[0].status).toBe('success');
		expect(mgr.files[1].status).toBe('error');
		expect(mgr.files[1].error).toBe('Rate limited');
		expect(mgr.isUploading).toBe(false);
	});

	// --- Multi-file: mixed valid + oversized ---

	it('validates per-file: oversized skipped, valid uploaded', async () => {
		const mgr = createUploadManager();
		mockUpload.mockResolvedValueOnce(UPLOAD_RESULT);

		const good = makeFile('photo.jpg', 1024);
		const tooBig = makeFile('huge.jpg', MAX_FILE_SIZE_BYTES + 1);
		await mgr.upload(makeFileList(good, tooBig), 'model', 'test');

		expect(mgr.files).toHaveLength(2);
		expect(mgr.files[0].status).toBe('success');
		expect(mgr.files[1].status).toBe('error');
		expect(mgr.files[1].error).toMatch(/size/i);
		expect(mockUpload).toHaveBeenCalledTimes(1);
	});

	// --- Options forwarding ---

	it('passes category and isPrimary to uploadMedia', async () => {
		const mgr = createUploadManager();
		mockUpload.mockResolvedValueOnce(UPLOAD_RESULT);

		const file = makeFile('photo.jpg');
		await mgr.upload(makeFileList(file), 'model', 'test', {
			category: 'backglass',
			isPrimary: true
		});

		expect(mockUpload).toHaveBeenCalledWith(
			file,
			'model',
			'test',
			{ category: 'backglass', isPrimary: true },
			expect.any(Function)
		);
	});

	// --- Reset ---

	it('reset clears all files', async () => {
		const mgr = createUploadManager();
		mockUpload.mockResolvedValueOnce(UPLOAD_RESULT);

		await mgr.upload(makeFileList(makeFile('a.jpg')), 'model', 'test');
		expect(mgr.files).toHaveLength(1);

		mgr.reset();
		expect(mgr.files).toEqual([]);
		expect(mgr.isUploading).toBe(false);
	});
});
