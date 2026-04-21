<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import TaxonomyListPage from '$lib/components/TaxonomyListPage.svelte';

	const loader = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/cabinets/');
		return data ?? [];
	}, []);
</script>

<TaxonomyListPage
	catalogKey="cabinet"
	subtitle="Physical cabinet styles used in pinball machines."
	items={loader.data}
	loading={loader.loading}
	error={loader.error}
	canCreate
/>
