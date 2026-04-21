<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import TaxonomyListPage from '$lib/components/TaxonomyListPage.svelte';

	const loader = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/display-subtypes/');
		return data ?? [];
	}, []);
</script>

<TaxonomyListPage
	catalogKey="display-subtype"
	subtitle="Specific variations of score display technologies."
	items={loader.data}
	loading={loader.loading}
	error={loader.error}
/>
