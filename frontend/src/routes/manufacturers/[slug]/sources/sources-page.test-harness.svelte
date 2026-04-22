<script lang="ts">
	import Page from './+page.svelte';
	import { setEntityContext } from '$lib/entity-context';

	let { data } = $props();

	setEntityContext({
		name: 'Williams',
		detailHref: '/manufacturers/williams'
	});
</script>

<Page {data} />
