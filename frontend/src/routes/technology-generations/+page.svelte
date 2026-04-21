<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import TaxonomyListPage from '$lib/components/TaxonomyListPage.svelte';

	const loader = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/technology-generations/');
		return data ?? [];
	}, []);
</script>

<TaxonomyListPage
	catalogKey="technology-generation"
	subtitle="Major eras of pinball technology."
	items={loader.data}
	loading={loader.loading}
	error={loader.error}
	canCreate
/>
