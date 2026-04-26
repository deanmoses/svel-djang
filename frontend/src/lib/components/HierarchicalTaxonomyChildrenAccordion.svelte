<script lang="ts">
  import { resolveHref } from '$lib/utils';
  import AccordionSection from '$lib/components/AccordionSection.svelte';
  import type { components } from '$lib/api/schema';

  type Ref = components['schemas']['Ref'];

  let {
    basePath,
    children,
    heading,
    headingSize,
  }: {
    basePath: string;
    children: Ref[];
    heading: string;
    headingSize?: string;
  } = $props();
</script>

{#if children.length > 0}
  <div class="mobile-only" data-testid="hierarchical-taxonomy-children-accordion">
    <AccordionSection {heading} {headingSize}>
      <ul class="children-list">
        {#each children as child (child.slug)}
          <li>
            <a href={resolveHref(`${basePath}/${child.slug}`)}>{child.name}</a>
          </li>
        {/each}
      </ul>
    </AccordionSection>
  </div>
{/if}

<style>
  /* Mobile-only: hidden at desktop breakpoint where the sidebar repeats this list. */
  /* Keep in sync with LAYOUT_BREAKPOINT (52rem). */
  @media (min-width: 52rem) {
    .mobile-only {
      display: none;
    }
  }

  .children-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--size-1);
  }
</style>
