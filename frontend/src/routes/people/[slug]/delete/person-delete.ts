/**
 * Person-specific bindings for the shared delete flow.
 *
 * All classification logic lives in :mod:`$lib/delete-flow`; this module
 * only names the endpoint and re-exports the entity's typed preview /
 * response schemas for page-level imports.
 */
import { createDeleteSubmitter } from '$lib/delete-flow';
import type { DeleteResponseSchema, PersonDeletePreviewSchema } from '$lib/api/schema';

export type DeletePreview = PersonDeletePreviewSchema;
export type DeleteResponse = DeleteResponseSchema;

export type { DeleteOutcome } from '$lib/delete-flow';

export const submitDelete = createDeleteSubmitter<DeleteResponse>(
  '/api/people/{public_id}/delete/',
);

export { submitUndoDelete, type UndoOutcome } from '$lib/undo-delete';
