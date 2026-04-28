import { resolve } from '$app/paths';
import { loadDeletePreview } from '$lib/delete-preview-loader';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params, url }) =>
  loadDeletePreview({
    fetch,
    url,
    slug: params.slug,
    entity: 'credit-roles',
    notFoundRedirect: resolve('/credit-roles'),
  });
