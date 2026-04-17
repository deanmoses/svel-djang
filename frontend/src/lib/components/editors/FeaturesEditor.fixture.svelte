<script lang="ts">
	import FeaturesEditor from './FeaturesEditor.svelte';

	type FeaturesModel = {
		game_format?: { slug: string } | null;
		cabinet?: { slug: string } | null;
		reward_types: { slug: string }[];
		tags: { slug: string }[];
		themes: { slug: string }[];
		production_quantity: string;
		player_count?: number | null;
		flipper_count?: number | null;
		gameplay_features: { slug: string; count?: number | null }[];
	};

	let {
		initialData,
		slug = 'medieval-madness'
	}: {
		initialData: FeaturesModel;
		slug?: string;
	} = $props();

	let dirtyFromCallback = $state(false);
	let dirtyFromHandle = $state('unknown');
	let savedCount = $state(0);
	let lastError = $state('');

	let editorRef:
		| {
				save(meta?: unknown): Promise<void>;
				isDirty(): boolean;
		  }
		| undefined = $state();
</script>

<FeaturesEditor
	bind:this={editorRef}
	{initialData}
	{slug}
	onsaved={() => savedCount++}
	onerror={(message) => (lastError = message)}
	ondirtychange={(dirty) => (dirtyFromCallback = dirty)}
/>

<button type="button" onclick={() => (dirtyFromHandle = String(editorRef?.isDirty() ?? false))}>
	Check dirty
</button>
<button type="button" onclick={() => editorRef?.save()}>Save</button>

<p data-testid="dirty-callback">{String(dirtyFromCallback)}</p>
<p data-testid="dirty-handle">{dirtyFromHandle}</p>
<p data-testid="saved-count">{savedCount}</p>
<p data-testid="last-error">{lastError}</p>
