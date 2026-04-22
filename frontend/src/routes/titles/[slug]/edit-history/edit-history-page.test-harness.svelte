<script lang="ts">
	import Page from './+page.svelte';
	import { setEntityContext } from '$lib/entity-context';

	let { data } = $props();

	setEntityContext({
		name: 'Medieval Madness',
		detailHref: '/titles/medieval-madness'
	});
</script>

<Page {data} />
