<script lang="ts">
	import RelationshipsEditor from './RelationshipsEditor.svelte';

	type RelationshipsModel = {
		variant_of?: { slug: string } | null;
		converted_from?: { slug: string } | null;
		remake_of?: { slug: string } | null;
	};

	let {
		initialModel,
		slug = 'medieval-madness'
	}: {
		initialModel: RelationshipsModel;
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

<RelationshipsEditor
	bind:this={editorRef}
	{initialModel}
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
