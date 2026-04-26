<script lang="ts">
  import type { Snippet } from 'svelte';

  type Width = 'default' | 'wide' | 'extra-wide';

  let {
    width = 'default',
    children,
  }: {
    width?: Width;
    children: Snippet;
  } = $props();
</script>

<article class={width}>
  {@render children()}
</article>

<style>
  article {
    max-width: 48rem;
  }

  article.wide {
    max-width: 56rem;
  }

  article.extra-wide {
    max-width: 64rem;
  }
</style>
