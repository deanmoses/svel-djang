<script lang="ts">
  import type { CreditSchema } from '$lib/api/schema';
  import PeopleEditor from './PeopleEditor.svelte';
  import type { SectionEditorHandle } from '$lib/components/pages/record/edit/editors/editor-contract';

  type Credit = CreditSchema;

  let {
    initialData = [],
    slug = 'medieval-madness',
  }: {
    initialData?: Credit[];
    slug?: string;
  } = $props();

  let savedCount = $state(0);
  let lastError = $state('');

  let editorRef: SectionEditorHandle | undefined = $state();

  let editorDirty = $derived(editorRef?.dirty ?? false);

  function handleSaved() {
    savedCount++;
  }

  function handleError(msg: string) {
    lastError = msg;
  }
</script>

<PeopleEditor
  bind:this={editorRef}
  {initialData}
  {slug}
  onsaved={handleSaved}
  onerror={handleError}
/>

<button type="button" onclick={() => editorRef?.save()}>Save</button>

<p data-testid="dirty">{String(editorDirty)}</p>
<p data-testid="saved-count">{savedCount}</p>
<p data-testid="last-error">{lastError}</p>
