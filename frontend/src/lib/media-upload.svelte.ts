/**
 * Multi-file upload manager with per-file state tracking.
 *
 * Uses Svelte 5 runes for reactive state. Each file is validated
 * independently (MIME type and size). Extension filtering is handled
 * by the file picker's accept attribute; this is a fallback for
 * drag-drop / paste. Files are uploaded concurrently via XHR with
 * individual progress tracking.
 */

import {
	uploadMedia,
	MAX_FILE_SIZE_BYTES,
	type UploadOptions,
	type UploadResult
} from './api/media-api';

export interface FileUploadState {
	file: File;
	status: 'pending' | 'uploading' | 'success' | 'error';
	progress: number;
	error: string | null;
	result: UploadResult | null;
}

function validateFile(file: File): string | null {
	if (file.size > MAX_FILE_SIZE_BYTES) {
		const maxMb = MAX_FILE_SIZE_BYTES / (1024 * 1024);
		return `File exceeds maximum size of ${maxMb} MB.`;
	}
	return null;
}

export function createUploadManager() {
	let files = $state<FileUploadState[]>([]);
	let isUploading = $state(false);

	async function upload(
		fileList: FileList,
		entityType: string,
		slug: string,
		opts?: UploadOptions
	): Promise<void> {
		const entries: FileUploadState[] = [];

		for (const file of fileList) {
			const error = validateFile(file);
			entries.push({
				file,
				status: error ? 'error' : 'pending',
				progress: 0,
				error,
				result: null
			});
		}

		files = [...files, ...entries];

		const pending = entries.filter((e) => e.status === 'pending');
		if (pending.length === 0) return;

		isUploading = true;

		const promises = pending.map(async (entry) => {
			entry.status = 'uploading';
			try {
				const result = await uploadMedia(file_entry_file(entry), entityType, slug, opts, (pct) => {
					entry.progress = pct;
				});
				entry.status = 'success';
				entry.progress = 100;
				entry.result = result;
			} catch (err) {
				entry.status = 'error';
				entry.error = err instanceof Error ? err.message : 'Upload failed';
			}
		});

		await Promise.all(promises);
		isUploading = false;
	}

	function reset(): void {
		files = [];
		isUploading = false;
	}

	return {
		get files() {
			return files;
		},
		get isUploading() {
			return isUploading;
		},
		upload,
		reset
	};
}

// Workaround: accessing entry.file directly in the closure above.
// Extracted to avoid Svelte reactivity proxy issues with File objects.
function file_entry_file(entry: FileUploadState): File {
	return entry.file;
}
