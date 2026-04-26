<script lang="ts">
  import { auth } from '$lib/auth.svelte';
  import { pageTitle } from '$lib/constants';
  import { resolveHref } from '$lib/utils';
  import PageActionBar from '$lib/components/PageActionBar.svelte';
  import RecordDetailShell from '$lib/components/RecordDetailShell.svelte';
  import SidebarList from '$lib/components/SidebarList.svelte';
  import SidebarListItem from '$lib/components/SidebarListItem.svelte';
  import SidebarSection from '$lib/components/SidebarSection.svelte';
  import type { Crumb } from '$lib/components/Breadcrumb.svelte';
  import type { EditSectionMenuItem } from '$lib/components/edit-section-menu';
  import { childrenHeading, newChildLabel, type LocationDetail } from './location-helpers';

  let { data, children } = $props();

  let profile = $derived<LocationDetail>(data.profile);
  let isRoot = $derived(profile.location_type === null);
  let path = $derived(profile.location_path);
  let displayName = $derived(profile.name || 'Locations');

  let breadcrumbs = $derived<Crumb[] | null>(
    isRoot
      ? null
      : [
          { label: 'Locations', href: '/locations' },
          ...profile.ancestors.map((a) => ({
            label: a.name,
            href: `/locations/${a.location_path}`,
          })),
        ],
  );

  let countText = $derived.by(() => {
    const n = profile.manufacturer_count;
    const noun = `manufacturer${n === 1 ? '' : 's'}`;
    const where = isRoot ? 'the world' : profile.name;
    return `There ${n === 1 ? 'has' : 'have'} been ${n} ${noun} in ${where}.`;
  });

  let editMenuItems = $derived.by<EditSectionMenuItem[]>(() => {
    if (isRoot) {
      return [{ key: 'new', label: '+ New Country', href: resolveHref('/locations/new') }];
    }
    const childLabel = newChildLabel(profile);
    const items: EditSectionMenuItem[] = [
      { key: 'name', label: 'Name', href: resolveHref(`/locations/${path}/edit/name`) },
      {
        key: 'desc',
        label: 'Description',
        href: resolveHref(`/locations/${path}/edit/description`),
      },
      { key: 'parent', label: 'Parent', href: resolveHref(`/locations/${path}/edit/parent`) },
      {
        key: 'aliases',
        label: 'Aliases',
        href: resolveHref(`/locations/${path}/edit/aliases`),
      },
    ];
    if (childLabel) {
      items.push({
        key: 'new',
        label: `+ New ${childLabel}`,
        href: resolveHref(`/locations/${path}/new`),
      });
    }
    items.push({
      key: 'delete',
      label: `Delete ${profile.name}`,
      href: resolveHref(`/locations/${path}/delete`),
      separatorBefore: true,
    });
    return items;
  });

  $effect(() => {
    void auth.load();
  });
</script>

<svelte:head>
  <title>{pageTitle(displayName)}</title>
</svelte:head>

{#snippet actionBar()}
  {#if isRoot}
    {#if auth.isAuthenticated}
      <PageActionBar editSections={editMenuItems} />
    {/if}
  {:else}
    <PageActionBar
      editSections={auth.isAuthenticated ? editMenuItems : undefined}
      historyHref={resolveHref(`/locations/${path}/edit-history`)}
      sourcesHref={resolveHref(`/locations/${path}/sources`)}
    />
  {/if}
{/snippet}

{#snippet sidebar()}
  {#if profile.children.length > 0}
    <SidebarSection heading={childrenHeading(profile.children)}>
      <SidebarList>
        {#each profile.children as child (child.location_path)}
          <SidebarListItem>
            <a href={resolveHref(`/locations/${child.location_path}`)}>
              {child.name}
            </a>
            <span class="count">{child.manufacturer_count}</span>
          </SidebarListItem>
        {/each}
      </SidebarList>
    </SidebarSection>
  {/if}
{/snippet}

<RecordDetailShell
  name={displayName}
  {breadcrumbs}
  metaItems={[{ text: countText }]}
  {actionBar}
  {sidebar}
>
  {#snippet main()}
    {@render children()}
  {/snippet}
</RecordDetailShell>

<style>
  .count {
    font-size: var(--font-size-0);
    color: var(--color-text-muted);
  }
</style>
