import type { SaveMeta } from './save-model-claims';

export type EditorDirtyChange = (dirty: boolean) => void;

export type SectionEditorHandle = {
	save(meta?: SaveMeta): Promise<void>;
	isDirty(): boolean;
};
