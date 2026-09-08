<script lang="ts">
  import ManufacturerBasicsEditor from './ManufacturerBasicsEditor.svelte';
  import type { ManufacturerEditView } from './manufacturer-edit-types';
  import type { SectionEditorHandle } from '$lib/components/pages/record/edit/editors/editor-contract';

  let {
    initialData = {
      name: 'Williams',
      slug: 'williams',
      website: 'https://williams.example',
      logo_url: 'https://williams.example/logo.png',
      description: {
        text: 'Historic manufacturer',
        plain: 'Historic manufacturer',
        html: '',
        citations: [],
      },
    },
    slug = 'williams',
  }: {
    initialData?: ManufacturerEditView;
    slug?: string;
  } = $props();

  let savedCount = $state(0);
  let lastError = $state('');

  let editorRef: SectionEditorHandle | undefined = $state();

  let editorDirty = $derived(editorRef?.dirty ?? false);
</script>

<ManufacturerBasicsEditor
  bind:this={editorRef}
  {initialData}
  {slug}
  onsaved={() => savedCount++}
  onerror={(message) => (lastError = message)}
/>

<button type="button" onclick={() => editorRef?.save()}>Save</button>

<p data-testid="dirty">{String(editorDirty)}</p>
<p data-testid="saved-count">{savedCount}</p>
<p data-testid="last-error">{lastError}</p>
