import { createDeleteSubmitter } from '$lib/delete-flow';
import type { DeleteResponseSchema } from '$lib/api/schema';

export type DeleteResponse = DeleteResponseSchema;

export const submitDelete = createDeleteSubmitter<DeleteResponse>(
  '/api/gameplay-features/{public_id}/delete/',
);
