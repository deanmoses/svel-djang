<script lang="ts">
	import BasicsEditor from './BasicsEditor.svelte';

	type BasicsModel = {
		name: string;
		slug: string;
		year?: number | null;
		month?: number | null;
		corporate_entity?: { slug: string } | null;
		abbreviations: string[];
	};

	let {
		initialModel,
		slug = 'medieval-madness'
	}: {
		initialModel: BasicsModel;
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

<BasicsEditor
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
