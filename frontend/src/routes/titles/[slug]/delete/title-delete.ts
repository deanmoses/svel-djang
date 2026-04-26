/**
 * Title-specific bindings for the shared delete flow.
 *
 * All classification logic lives in :mod:`$lib/delete-flow`; this module
 * only names the endpoint and re-exports the entity's typed preview /
 * response schemas for page-level imports.
 */
import { createDeleteSubmitter } from '$lib/delete-flow';
import type { components } from '$lib/api/schema';

export type DeletePreview = components['schemas']['TitleDeletePreviewSchema'];
export type DeleteResponse = components['schemas']['TitleDeleteResponseSchema'];

export type { DeleteOutcome } from '$lib/delete-flow';

export const submitDelete = createDeleteSubmitter<DeleteResponse>('/api/titles/{slug}/delete/');

export { submitUndoDelete, type UndoOutcome } from '$lib/undo-delete';
