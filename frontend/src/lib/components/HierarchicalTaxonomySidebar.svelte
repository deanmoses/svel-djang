<script lang="ts">
  import { resolveHref } from '$lib/utils';
  import SidebarList from '$lib/components/SidebarList.svelte';
  import SidebarListItem from '$lib/components/SidebarListItem.svelte';
  import SidebarSection from '$lib/components/SidebarSection.svelte';
  import type { components } from '$lib/api/schema';

  type Ref = components['schemas']['Ref'];

  let {
    basePath,
    parents,
    children,
    aliases,
    parentHeading,
    childHeading,
    aliasHeading = 'Also known as',
  }: {
    basePath: string;
    parents: Ref[];
    children: Ref[];
    aliases: string[];
    parentHeading: string;
    childHeading: string;
    aliasHeading?: string;
  } = $props();
</script>

{#if parents.length > 0}
  <SidebarSection heading={parentHeading}>
    <SidebarList>
      {#each parents as parent (parent.slug)}
        <SidebarListItem>
          <a href={resolveHref(`${basePath}/${parent.slug}`)}>{parent.name}</a>
        </SidebarListItem>
      {/each}
    </SidebarList>
  </SidebarSection>
{/if}

{#if children.length > 0}
  <SidebarSection heading={childHeading}>
    <SidebarList>
      {#each children as child (child.slug)}
        <SidebarListItem>
          <a href={resolveHref(`${basePath}/${child.slug}`)}>{child.name}</a>
        </SidebarListItem>
      {/each}
    </SidebarList>
  </SidebarSection>
{/if}

{#if aliases.length > 0}
  <SidebarSection heading={aliasHeading}>
    <p class="aliases">{aliases.join(', ')}</p>
  </SidebarSection>
{/if}

<style>
  .aliases {
    font-size: var(--font-size-0);
    color: var(--color-text-muted);
    margin: 0;
  }
</style>
