/**
 * Entity-agnostic client shim for the Undo-ChangeSet endpoint.
 *
 * The backend endpoint ``/api/edit-history/undo-changeset/`` inverts any
 * DELETE ChangeSet atomically, regardless of which entity types it
 * touched. The caller only needs the ChangeSet id and a note, so a single
 * helper is reused across every record-type delete flow (Title, Model, …).
 */

import client from '$lib/api/client';
import { parseApiError } from '$lib/components/editors/save-claims-shared';

export type UndoOutcome =
	| { kind: 'ok'; changesetId: number }
	| { kind: 'superseded'; message: string }
	| { kind: 'form_error'; message: string };

export async function submitUndoDelete(changesetId: number, note = ''): Promise<UndoOutcome> {
	const { data, error, response } = await client.POST('/api/edit-history/undo-changeset/', {
		body: { changeset_id: changesetId, note }
	});

	if (response.status === 422) {
		// The most common 422 from undo is "not the latest action anymore".
		return {
			kind: 'superseded',
			message: "This delete is no longer the latest action — can't undo automatically."
		};
	}

	if (error || !data) {
		const parsed = parseApiError(error);
		return { kind: 'form_error', message: parsed.message || 'Undo failed.' };
	}

	const cs = (data as { changeset_id?: number }).changeset_id;
	return { kind: 'ok', changesetId: cs ?? changesetId };
}
