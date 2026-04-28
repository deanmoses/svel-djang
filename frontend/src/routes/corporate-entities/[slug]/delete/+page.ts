import { resolve } from '$app/paths';
import { loadDeletePreview } from '$lib/delete-preview-loader';
import type { PageLoad } from './$types';

// The preview already carries `parent` because the CE registrar was wired
// with parent_field="manufacturer" — no separate detail fetch needed.
export const load: PageLoad = ({ fetch, params, url }) =>
  loadDeletePreview({
    fetch,
    url,
    slug: params.slug,
    entity: 'corporate-entities',
    notFoundRedirect: resolve('/corporate-entities'),
  });
