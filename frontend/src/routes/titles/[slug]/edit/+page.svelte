<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { defaultTitleSectionSegment } from '$lib/components/editors/title-edit-sections';

	let { data } = $props();
	let isSingleModel = $derived(!!data.title.model_detail);

	$effect(() => {
		goto(resolve(`/titles/${page.params.slug}/edit/${defaultTitleSectionSegment(isSingleModel)}`), {
			replaceState: true
		});
	});
</script>
