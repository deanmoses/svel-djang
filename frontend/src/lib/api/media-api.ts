/**
 * Media API client — upload, detach, and set-primary.
 *
 * Upload uses XMLHttpRequest for progress events.
 * Detach and set-primary use fetch (no progress needed).
 */

import type { UploadSchema } from './schema';
import { getCsrfToken } from './client';
import { parseApiError } from './parse-api-error';

export type UploadResult = UploadSchema;

// Keep in sync: backend/apps/media/constants.py
export const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB
export const IMAGE_ACCEPT = 'image/*,.heic,.heif,.avif';

// ---------------------------------------------------------------------------
// Upload (XHR for progress)
// ---------------------------------------------------------------------------

export interface UploadOptions {
  category?: string;
  isPrimary?: boolean;
}

export class UploadError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'UploadError';
  }
}

export function uploadMedia(
  file: File,
  entityType: string,
  publicId: string,
  opts?: UploadOptions,
  onProgress?: (pct: number) => void,
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('file', file);
    form.append('entity_type', entityType);
    form.append('public_id', publicId);
    if (opts?.category) form.append('category', opts.category);
    if (opts?.isPrimary) form.append('is_primary', 'true');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/media/upload/');

    const token = getCsrfToken();
    if (token) xhr.setRequestHeader('X-CSRFToken', token);

    if (onProgress) {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });
    }

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as UploadResult);
      } else {
        let message = `Upload failed (${xhr.status})`;
        try {
          const body = JSON.parse(xhr.responseText);
          const parsed = parseApiError(body).message;
          if (parsed) message = parsed;
        } catch {
          // ignore parse errors
        }
        reject(new UploadError(message, xhr.status));
      }
    });

    xhr.addEventListener('error', () => {
      reject(new UploadError('Network error during upload', 0));
    });

    xhr.send(form);
  });
}

// ---------------------------------------------------------------------------
// Detach + set-primary (fetch, shared request shape)
// ---------------------------------------------------------------------------

async function mediaAction(
  endpoint: string,
  entityType: string,
  publicId: string,
  assetUuid: string,
): Promise<void> {
  const token = getCsrfToken();
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify({
      entity_type: entityType,
      public_id: publicId,
      asset_uuid: assetUuid,
    }),
  });
  if (!resp.ok) {
    let message = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      const parsed = parseApiError(body).message;
      if (parsed) message = parsed;
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
}

export function detachMedia(
  entityType: string,
  publicId: string,
  assetUuid: string,
): Promise<void> {
  return mediaAction('/api/media/detach/', entityType, publicId, assetUuid);
}

export function setPrimary(entityType: string, publicId: string, assetUuid: string): Promise<void> {
  return mediaAction('/api/media/set-primary/', entityType, publicId, assetUuid);
}
