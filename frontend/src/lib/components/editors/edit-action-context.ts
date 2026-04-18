import { getContext, setContext } from 'svelte';
import type { CombinedSectionKey } from './combined-edit-sections';
import type { ManufacturerEditSectionKey } from './manufacturer-edit-sections';
import type { ModelEditSectionKey } from './model-edit-sections';

export type EditActionFn<TKey extends string> = (key: TKey) => (() => void) | undefined;

type EditActionContext<TKey extends string> = {
	set: (fn: EditActionFn<TKey>) => void;
	get: () => EditActionFn<TKey>;
	setForTesting: (fn: EditActionFn<TKey>) => void;
};

function createEditActionContext<TKey extends string>(
	name: string,
	missingMessage: string
): EditActionContext<TKey> {
	const key = Symbol(name);

	return {
		set(fn) {
			setContext(key, fn);
		},
		get() {
			const fn = getContext<EditActionFn<TKey> | undefined>(key);
			if (!fn) throw new Error(missingMessage);
			return fn;
		},
		setForTesting(fn) {
			setContext<EditActionFn<TKey>>(key, fn);
		}
	};
}

export const modelEditActionContext = createEditActionContext<ModelEditSectionKey>(
	'modelEditAction',
	'modelEditAction context missing — must be rendered inside the model layout'
);

export const manufacturerEditActionContext = createEditActionContext<ManufacturerEditSectionKey>(
	'manufacturerEditAction',
	'manufacturerEditAction context missing — must be rendered inside the manufacturer layout'
);

/**
 * Title-area context — used on the Title reader where the combined menu spans
 * both title- and model-tier sections. Keys are composite (e.g. 'title:basics',
 * 'model:overview').
 */
export const titleAreaEditActionContext = createEditActionContext<CombinedSectionKey>(
	'titleAreaEditAction',
	'titleAreaEditAction context missing — must be rendered inside the title layout'
);
