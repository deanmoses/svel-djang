/**
 * API client for wikilink autocomplete endpoints.
 */

import client from './client';
import type { LinkTypeSchema, LinkTargetSchema } from './schema';

export type LinkType = LinkTypeSchema;
export type LinkTarget = LinkTargetSchema;

// Module-level cache — link types don't change at runtime.
let cachedTypes: LinkType[] | null = null;

/** Reset cache — for tests only. */
export function _resetCache(): void {
  cachedTypes = null;
}

export async function fetchLinkTypes(): Promise<LinkType[]> {
  if (cachedTypes) return cachedTypes;

  const { data, response } = await client.GET('/api/link-types/');
  if (!data) {
    throw new Error(`Failed to fetch link types: ${response.status}`);
  }

  cachedTypes = data;
  return cachedTypes;
}

export async function searchLinkTargets(
  type: string,
  query: string,
): Promise<{ results: LinkTarget[] }> {
  const { data, response } = await client.GET('/api/link-types/targets/', {
    params: { query: { type, q: query } },
  });
  if (!data) {
    throw new Error(`Failed to search link targets: ${response.status}`);
  }
  return data;
}
