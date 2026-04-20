/**
 * Shared business rules derived from the data model and UX spec.
 *
 * Rules live here when they're referenced from multiple places in the
 * frontend and we want a single source of truth for the definition.
 */

/**
 * True when the given model's identity fields (name, slug, abbreviations)
 * live on the Title row rather than the Model row.
 *
 * Per ModelAndTitleUX.md "Single-Model Title Edit", this is the case exactly
 * when the Title reader inlines this model's detail — i.e. the canonical
 * single-inline condition also used by the /models/{slug} → /titles/{slug}
 * redirect in +page.server.ts:
 *
 *   - the model is a base model (not a variant), AND
 *   - its title has exactly one base model (this one), AND
 *   - that base model has no variants.
 *
 * A base model with variants does NOT qualify: the Title reader doesn't
 * show a combined editor in that case, so the model's identity must stay
 * editable from the Model page. Earlier versions keyed off
 * title_models.length <= 1, which incorrectly hid identity editors from
 * base-model-plus-variants titles.
 */
export function modelHasTitleOwnedIdentity(model: {
	title_models: readonly { variants: readonly unknown[] }[];
	variant_of?: unknown | null;
}): boolean {
	if (model.variant_of) return false;
	if (model.title_models.length !== 1) return false;
	return model.title_models[0].variants.length === 0;
}
