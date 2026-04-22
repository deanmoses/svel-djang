<script lang="ts">
	import Page from './+page.svelte';
	import { setEntityContext } from '$lib/entity-context';

	let { data } = $props();

	setEntityContext({
		name: 'Standard Body',
		detailHref: '/cabinets/standard-body'
	});
</script>

<Page {data} />
