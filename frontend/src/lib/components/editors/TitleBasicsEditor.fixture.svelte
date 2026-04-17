<script lang="ts">
	import TitleBasicsEditor from './TitleBasicsEditor.svelte';

	type BasicsTitle = {
		name: string;
		slug: string;
		franchise?: { slug: string } | null;
		series?: { slug: string } | null;
		abbreviations: string[];
	};

	let {
		initialData,
		slug = 'addams-family'
	}: {
		initialData: BasicsTitle;
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

<TitleBasicsEditor
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
