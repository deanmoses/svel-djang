import { resolve } from '$app/paths';
import { loadDeletePreview } from '$lib/delete-preview-loader';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params, url }) =>
  loadDeletePreview({
    fetch,
    url,
    public_id: params.path,
    entity: 'locations',
    notFoundRedirect: resolve('/locations'),
  });
