import type { components } from '$lib/api/schema';
import type { SaveResult } from './save-claims-shared';

type RichTextSchema = components['schemas']['RichTextSchema'];

/**
 * Structural superset of GameplayFeatureDetailSchema and ThemeDetailSchema —
 * the fields the hierarchical-taxonomy section editors consume.
 */
export type HierarchicalTaxonomyEditView = {
	name: string;
	slug: string;
	description: RichTextSchema;
	parents: { name: string; slug: string }[];
	aliases: string[];
};

type ClaimsBody = components['schemas']['HierarchyClaimPatchSchema'];

export type HierarchicalTaxonomySectionPatchBody = Partial<
	Pick<ClaimsBody, 'fields' | 'parents' | 'aliases' | 'note' | 'citation'>
>;

export type SaveHierarchicalTaxonomyClaims = (
	slug: string,
	body: HierarchicalTaxonomySectionPatchBody
) => Promise<SaveResult>;
