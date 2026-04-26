<script>
  import Page from '$lib/components/Page.svelte';

  let { children } = $props();
</script>

<Page>
  <div class="prose">
    {@render children()}
  </div>
</Page>

<style>
  .prose :global(h1) {
    font-size: var(--font-size-7);
    font-weight: 700;
    color: var(--color-text-primary);
    margin-bottom: var(--size-2);
  }

  .prose :global(h2) {
    font-size: var(--font-size-4);
    font-weight: 600;
    color: var(--color-text-primary);
    margin-top: var(--size-7);
    margin-bottom: var(--size-3);
  }

  .prose :global(h3) {
    font-size: var(--font-size-3);
    font-weight: 600;
    color: var(--color-text-primary);
    margin-top: var(--size-5);
    margin-bottom: var(--size-2);
  }

  .prose :global(p) {
    font-size: var(--font-size-2);
    line-height: var(--font-lineheight-3);
    color: var(--color-text-primary);
    margin-bottom: var(--size-4);
  }

  .prose :global(ul),
  .prose :global(ol) {
    font-size: var(--font-size-2);
    line-height: var(--font-lineheight-3);
    padding-left: var(--size-5);
    margin-bottom: var(--size-4);
  }

  .prose :global(li) {
    margin-bottom: var(--size-2);
  }

  .prose :global(.last-updated) {
    font-size: var(--font-size-1);
    color: var(--color-text-muted);
    margin-bottom: var(--size-6);
  }
</style>
