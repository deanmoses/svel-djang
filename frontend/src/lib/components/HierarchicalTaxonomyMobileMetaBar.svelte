<script lang="ts">
  import { resolveHref } from '$lib/utils';
  import type { components } from '$lib/api/schema';

  type Ref = components['schemas']['Ref'];

  let {
    basePath,
    parents,
    aliases,
    parentLabel,
    aliasLabel = 'Also known as',
  }: {
    basePath: string;
    parents: Ref[];
    aliases: string[];
    parentLabel: string;
    aliasLabel?: string;
  } = $props();

  let hasContent = $derived(parents.length > 0 || aliases.length > 0);
</script>

{#if hasContent}
  <p class="meta-bar" data-testid="hierarchical-taxonomy-mobile-meta-bar">
    {#if parents.length > 0}
      <span class="part">
        <span class="label">{parentLabel}:</span>
        {#each parents as parent, i (parent.slug)}
          {#if i > 0}<span class="sep">, </span>{/if}
          <a href={resolveHref(`${basePath}/${parent.slug}`)}>{parent.name}</a>
        {/each}
      </span>
    {/if}
    {#if parents.length > 0 && aliases.length > 0}
      <span class="separator" aria-hidden="true">·</span>
    {/if}
    {#if aliases.length > 0}
      <span class="part">
        <span class="label">{aliasLabel}:</span>
        {aliases.join(', ')}
      </span>
    {/if}
  </p>
{/if}

<style>
  /* Mobile-only: hidden at desktop breakpoint where the sidebar repeats this info. */
  /* Keep in sync with LAYOUT_BREAKPOINT (52rem). */
  .meta-bar {
    display: flex;
    flex-wrap: wrap;
    gap: var(--size-2);
    font-size: var(--font-size-0);
    color: var(--color-text-muted);
    margin: 0 0 var(--size-4);
  }

  @media (min-width: 52rem) {
    .meta-bar {
      display: none;
    }
  }

  .label {
    font-weight: 600;
    color: var(--color-text-primary);
    margin-right: var(--size-1);
  }

  .separator {
    color: var(--color-text-muted);
  }
</style>
