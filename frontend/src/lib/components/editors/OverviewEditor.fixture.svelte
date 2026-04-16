<script lang="ts">
	import OverviewEditor from './OverviewEditor.svelte';

	let dirtyFromCallback = $state(false);
	let dirtyFromHandle = $state('unknown');
	let savedCount = $state(0);
	let lastError = $state('');

	let editorRef:
		| {
				save(): Promise<void>;
				isDirty(): boolean;
		  }
		| undefined = $state();

	function handleDirtyChange(dirty: boolean) {
		dirtyFromCallback = dirty;
	}
</script>

<OverviewEditor
	bind:this={editorRef}
	initialDescription="Original description"
	slug="medieval-madness"
	onsaved={() => savedCount++}
	onerror={(message) => (lastError = message)}
	ondirtychange={handleDirtyChange}
/>

<button type="button" onclick={() => (dirtyFromHandle = String(editorRef?.isDirty() ?? false))}>
	Check dirty
</button>
<button type="button" onclick={() => editorRef?.save()}>Save</button>

<p data-testid="dirty-callback">{String(dirtyFromCallback)}</p>
<p data-testid="dirty-handle">{dirtyFromHandle}</p>
<p data-testid="saved-count">{savedCount}</p>
<p data-testid="last-error">{lastError}</p>
