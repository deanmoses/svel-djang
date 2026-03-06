import { resolve } from '$app/paths';

/** Wrapper around resolve() that accepts a plain string (for dynamic URLs). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const resolveHref = (url: string) => resolve(url as any);
