/**
 * Generic client shim for catalog soft-delete endpoints.
 *
 * Title, Model, and Person (and every future lifecycle entity) all hit a
 * ``POST /api/{collection}/{slug}/delete/`` endpoint with the same request
 * body shape and the same 200 / 422 / 429 response taxonomy. The only
 * per-entity variations are the endpoint path and the typed success body,
 * so this module owns the shared classification and each entity's
 * ``{entity}-delete.ts`` binds a typed ``submitDelete`` via
 * :func:`createDeleteSubmitter`.
 */
import client from '$lib/api/client';
import { parseApiError } from '$lib/components/editors/save-claims-shared';
import type { components } from '$lib/api/schema';
import type { EditCitationSelection } from '$lib/edit-citation';
import { buildEditCitationRequest } from '$lib/edit-citation';

export type BlockingReferrer = components['schemas']['BlockingReferrerSchema'];

export type DeleteOutcome<TResponse> =
	| { kind: 'ok'; data: TResponse }
	| { kind: 'rate_limited'; retryAfterSeconds: number; message: string }
	| {
			kind: 'blocked';
			blockedBy: BlockingReferrer[];
			message: string;
			// Escape hatch for entity-specific fields the 422 body may carry
			// (e.g. Person's ``active_credit_count``). Entries not emitted by
			// the backend are simply absent.
			extra: Record<string, unknown>;
	  }
	| { kind: 'form_error'; message: string };

export interface DeleteSubmitOptions {
	note?: string;
	citation?: EditCitationSelection | null;
}

type DeleteEndpoint = `/api/${string}/{slug}/delete/`;

export function createDeleteSubmitter<TResponse>(endpoint: DeleteEndpoint) {
	return async (
		slug: string,
		opts: DeleteSubmitOptions = {}
	): Promise<DeleteOutcome<TResponse>> => {
		// openapi-fetch's typed POST doesn't let us parameterize the path at
		// compile time with an arbitrary string. Each caller has already
		// asserted the endpoint matches a real route via the typed wrapper,
		// so the ``as never`` cast here is localized and safe.
		const { data, error, response } = await client.POST(
			endpoint as never,
			{
				params: { path: { slug } },
				body: {
					note: opts.note ?? '',
					citation: buildEditCitationRequest(opts.citation ?? null)
				}
			} as never
		);

		if (response.status === 429) {
			const retryAfter = Number(response.headers.get('Retry-After') ?? '86400');
			const hours = Math.max(1, Math.round(retryAfter / 3600));
			return {
				kind: 'rate_limited',
				retryAfterSeconds: retryAfter,
				message: `You've reached the delete limit. Try again in about ${hours} hour${hours === 1 ? '' : 's'}.`
			};
		}

		if (response.status === 422) {
			const body = (await response
				.clone()
				.json()
				.catch(() => null)) as
				| ({ blocked_by?: BlockingReferrer[]; detail?: unknown } & Record<string, unknown>)
				| null;
			if (body && Array.isArray(body.blocked_by)) {
				const { blocked_by, detail, ...extra } = body;
				return {
					kind: 'blocked',
					blockedBy: blocked_by,
					message:
						typeof detail === 'string'
							? detail
							: 'Cannot delete: active references would be left dangling.',
					extra
				};
			}
		}

		if (error || !data) {
			const parsed = parseApiError(error);
			return { kind: 'form_error', message: parsed.message || 'Could not delete record.' };
		}

		return { kind: 'ok', data: data as TResponse };
	};
}

export { submitUndoDelete, type UndoOutcome } from '$lib/undo-delete';
