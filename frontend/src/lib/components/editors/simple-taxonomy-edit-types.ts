import type { components } from '$lib/api/schema';
import type { SaveResult } from './save-claims-shared';

type RichTextSchema = components['schemas']['RichTextSchema'];

/**
 * Structural superset of every per-entity page payload (TaxonomySchema,
 * RewardTypeDetailSchema, etc). Each of those schemas already includes
 * these four fields, so all per-entity profiles are assignable to this
 * view without picking the "right" schema.
 */
export type SimpleTaxonomyEditView = {
	name: string;
	slug: string;
	description: RichTextSchema;
	display_order: number | null;
};

type ClaimsBody = components['schemas']['ClaimPatchSchema'];

export type SimpleTaxonomySectionPatchBody = Partial<
	Pick<ClaimsBody, 'fields' | 'note' | 'citation'>
>;

export type SaveSimpleTaxonomyClaims = (
	slug: string,
	body: SimpleTaxonomySectionPatchBody
) => Promise<SaveResult>;
