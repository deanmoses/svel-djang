<script lang="ts">
  import type { Snippet } from 'svelte';
  import HeroHeader from '$lib/components/HeroHeader.svelte';
  import type { Crumb } from '$lib/components/Breadcrumb.svelte';
  import Page from '$lib/components/Page.svelte';
  import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';

  type MetaItem = { text: string; href?: string };
  type ParentLink = { text: string; href: string };

  let {
    name,
    heroImageUrl = null,
    heroImageAlt = '',
    parentLink = null,
    breadcrumbs = null,
    metaItems = [],
    aliases = [],
    sidebarDesktopOnly = false,
    actionBar,
    main: mainContent,
    sidebar: sidebarContent,
  }: {
    name: string;
    heroImageUrl?: string | null;
    heroImageAlt?: string;
    parentLink?: ParentLink | null;
    /** Breadcrumb trail. Mutually exclusive with `parentLink`. */
    breadcrumbs?: Crumb[] | null;
    metaItems?: MetaItem[];
    aliases?: string[];
    /**
     * When true, hides the sidebar on mobile. Default `false` stacks
     * the sidebar below the main column on mobile — correct only when
     * the sidebar's content isn't already visible elsewhere on mobile.
     * Pass `isDetail` when the main column duplicates sidebar content
     * via a mobile meta bar / children accordion / relationships
     * accordion; otherwise mobile renders the sidebar content twice.
     */
    sidebarDesktopOnly?: boolean;
    actionBar?: Snippet;
    main: Snippet;
    sidebar?: Snippet;
  } = $props();

  if (import.meta.env.DEV) {
    $effect(() => {
      if (parentLink && breadcrumbs) {
        console.warn(
          'RecordDetailShell: parentLink and breadcrumbs are mutually exclusive; breadcrumbs wins',
        );
      }
    });
  }
</script>

<Page width="extra-wide">
  <HeroHeader
    {name}
    {heroImageUrl}
    {heroImageAlt}
    {parentLink}
    {breadcrumbs}
    {metaItems}
    {aliases}
  />

  {#if actionBar}
    {@render actionBar()}
  {/if}

  {#if sidebarContent}
    <TwoColumnLayout>
      {#snippet main()}
        {@render mainContent()}
      {/snippet}

      {#snippet sidebar()}
        {#if sidebarDesktopOnly}
          <div class="desktop-only">
            {@render sidebarContent()}
          </div>
        {:else}
          {@render sidebarContent()}
        {/if}
      {/snippet}
    </TwoColumnLayout>
  {:else}
    {@render mainContent()}
  {/if}
</Page>

<style>
  /* Hide sidebar on mobile for the detail reader — the page body duplicates it. */
  /* Keep in sync with LAYOUT_BREAKPOINT (52rem). */
  .desktop-only {
    display: none;
  }

  @media (min-width: 52rem) {
    .desktop-only {
      display: contents;
    }
  }
</style>
