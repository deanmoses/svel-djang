<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	$effect(() => {
		goto(resolve(`/models/${page.params.slug}/edit/basics`), { replaceState: true });
	});
</script>
