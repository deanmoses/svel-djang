<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import TaxonomyListPage from '$lib/components/TaxonomyListPage.svelte';

	const loader = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/themes/');
		return data ?? [];
	}, []);
</script>

<TaxonomyListPage
	catalogKey="theme"
	subtitle="Thematic categories for pinball machines."
	items={loader.data}
	loading={loader.loading}
	error={loader.error}
	canCreate
/>
