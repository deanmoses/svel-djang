<script lang="ts">
	import DeletePage from '$lib/components/DeletePage.svelte';
	import type { BlockedState } from '$lib/components/delete-page';
	import type { BlockingReferrer } from '$lib/delete-flow';
	import { pluralize } from '$lib/utils';
	import { submitDelete } from './manufacturer-delete';

	let { data } = $props();
	let { preview, slug } = $derived(data);

	let blockedReferrers = $derived(preview.blocked_by ?? []);

	function referrerHref(r: BlockingReferrer): string | null {
		if (!r.slug) return null;
		switch (r.entity_type) {
			case 'corporate-entity':
				return `/corporate-entities/${r.slug}`;
			case 'system':
				return `/systems/${r.slug}`;
			case 'model':
				return `/models/${r.slug}`;
			default:
				return null;
		}
	}

	let blocked = $derived<BlockedState | null>(
		blockedReferrers.length > 0
			? {
					kind: 'referrers',
					lead: "This manufacturer can't be deleted because active records still point at it:",
					referrers: blockedReferrers,
					renderReferrerHref: referrerHref,
					renderReferrerHint: (r: BlockingReferrer) =>
						`references this manufacturer via ${r.relation}`,
					footer: 'Resolve these references, then try again.'
				}
			: null
	);

	let impact = $derived({
		items: ['this manufacturer', pluralize(preview.changeset_count, 'change set')],
		note: 'You can undo this from the toast that appears on the manufacturers page, or restore the record later from its edit history.'
	});
</script>

<DeletePage
	entityLabel="Manufacturer"
	entityName={preview.name}
	{slug}
	submit={submitDelete}
	cancelHref={`/manufacturers/${slug}`}
	redirectAfterDelete="/manufacturers"
	editHistoryHref={`/manufacturers/${slug}/edit-history`}
	{blocked}
	{impact}
/>
