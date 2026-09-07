/** The menu/listbox role `ActionMenu` publishes so its `MenuItem` descendants render matching ARIA semantics. */
import { createContext } from 'svelte';

export type MenuRole = 'menu' | 'listbox';

const [read, write, has] = createContext<MenuRole>();

export function setMenuRole(role: MenuRole): void {
  write(role);
}

/** Falls back to 'menu' when no `ActionMenu` ancestor set a role, so a `MenuItem` is never role-less. */
export function getMenuRole(): MenuRole {
  return has() ? read() : 'menu';
}
