import { createContext } from 'svelte';

type EditLayoutContext = {
  setDirty: (dirty: boolean) => void;
};

const [read, write, has] = createContext<EditLayoutContext>();

export function setEditLayoutContext(context: EditLayoutContext): void {
  write(context);
}

export function getEditLayoutContext(): EditLayoutContext {
  if (!has()) {
    throw new Error('editLayout context missing — must be rendered inside an edit section layout');
  }
  return read();
}
