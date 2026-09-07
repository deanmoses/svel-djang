import { createContext } from 'svelte';
import type { CombinedSectionKey } from './combined-edit-sections';
import type { CorporateEntityEditSectionKey } from '$lib/components/pages/record/edit/editors/entity/corporate-entity/corporate-entity-edit-sections';
import type { HierarchicalTaxonomyEditSectionKey } from '$lib/components/pages/record/edit/editors/entity/taxonomy/hierarchical-taxonomy-edit-sections';
import type { LocationEditSectionKey } from '$lib/components/pages/record/edit/editors/entity/location/location-edit-sections';
import type { ManufacturerEditSectionKey } from '$lib/components/pages/record/edit/editors/entity/manufacturer/manufacturer-edit-sections';
import type { ModelEditSectionKey } from '$lib/components/pages/record/edit/editors/entity/model/model-edit-sections';
import type { PersonEditSectionKey } from '$lib/components/pages/record/edit/editors/entity/person/person-edit-sections';

export type EditActionFn<TKey extends string> = (key: TKey) => (() => void) | undefined;

export type EditActionContext<TKey extends string> = {
  set: (fn: EditActionFn<TKey>) => void;
  get: () => EditActionFn<TKey>;
  setForTesting: (fn: EditActionFn<TKey>) => void;
};

function createEditActionContext<TKey extends string>(
  missingMessage: string,
): EditActionContext<TKey> {
  const [read, write, has] = createContext<EditActionFn<TKey>>();

  return {
    set(fn) {
      write(fn);
    },
    get() {
      if (!has()) throw new Error(missingMessage);
      return read();
    },
    setForTesting(fn) {
      write(fn);
    },
  };
}

export const modelEditActionContext = createEditActionContext<ModelEditSectionKey>(
  'modelEditAction context missing — must be rendered inside the model layout',
);

export const manufacturerEditActionContext = createEditActionContext<ManufacturerEditSectionKey>(
  'manufacturerEditAction context missing — must be rendered inside the manufacturer layout',
);

export const corporateEntityEditActionContext =
  createEditActionContext<CorporateEntityEditSectionKey>(
    'corporateEntityEditAction context missing — must be rendered inside the corporate-entity layout',
  );

export const personEditActionContext = createEditActionContext<PersonEditSectionKey>(
  'personEditAction context missing — must be rendered inside the person layout',
);

export const locationEditActionContext = createEditActionContext<LocationEditSectionKey>(
  'locationEditAction context missing — must be rendered inside the location layout',
);

/**
 * Title-area context — used on the Title reader where the combined menu spans
 * both title- and model-tier sections. Keys are composite (e.g. 'title:name',
 * 'model:overview').
 */
export const titleAreaEditActionContext = createEditActionContext<CombinedSectionKey>(
  'titleAreaEditAction context missing — must be rendered inside the title layout',
);

/**
 * Hierarchical-taxonomy context — shared between gameplay-features and themes.
 * Both entities' detail layouts publish an editAction; their +page.svelte
 * accordions retrieve it for [edit] affordances (e.g. the Media accordion on
 * gameplay-features). Themes calling editAction('media') returns undefined
 * because no 'media' section is registered for it; safe because themes never
 * renders the Media accordion.
 */
export const hierarchicalTaxonomyEditActionContext =
  createEditActionContext<HierarchicalTaxonomyEditSectionKey>(
    'hierarchicalTaxonomyEditAction context missing — must be rendered inside the gameplay-features or themes layout',
  );
