<script lang="ts">
  import SystemTechnologyEditor from './SystemTechnologyEditor.svelte';
  import { saveSystemClaims } from './save-system-claims';
  import type { SectionEditorHandle } from '$lib/components/pages/record/edit/editors/editor-contract';

  type InitialData = {
    technology_subgeneration?: { public_id: string } | null;
  };

  let {
    initialData,
    slug = 'wpc-95',
  }: {
    initialData: InitialData;
    slug?: string;
  } = $props();

  let savedCount = $state(0);
  let lastError = $state('');

  let editorRef: SectionEditorHandle | undefined = $state();

  let editorDirty = $derived(editorRef?.dirty ?? false);
</script>

<SystemTechnologyEditor
  bind:this={editorRef}
  {initialData}
  {slug}
  save={saveSystemClaims}
  onsaved={() => savedCount++}
  onerror={(message) => (lastError = message)}
/>

<button type="button" onclick={() => editorRef?.save()}>Save</button>

<p data-testid="dirty">{String(editorDirty)}</p>
<p data-testid="saved-count">{savedCount}</p>
<p data-testid="last-error">{lastError}</p>
