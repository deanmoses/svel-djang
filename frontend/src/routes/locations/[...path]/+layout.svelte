<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { auth } from '$lib/auth.svelte';
  import { LAYOUT_BREAKPOINT, pageTitle } from '$lib/constants';
  import { resolveHref } from '$lib/utils';
  import PageActionBar from '$lib/components/PageActionBar.svelte';
  import RecordDetailShell from '$lib/components/RecordDetailShell.svelte';
  import SectionEditorHost from '$lib/components/SectionEditorHost.svelte';
  import SidebarList from '$lib/components/SidebarList.svelte';
  import SidebarListItem from '$lib/components/SidebarListItem.svelte';
  import SidebarSection from '$lib/components/SidebarSection.svelte';
  import type { Crumb } from '$lib/components/Breadcrumb.svelte';
  import type { EditSectionMenuItem } from '$lib/components/edit-section-menu';
  import {
    findLocationSectionByKey,
    findLocationSectionBySegment,
    locationEditSectionsFor,
    type LocationEditSectionDef,
    type LocationEditSectionKey,
  } from '$lib/components/editors/location-edit-sections';
  import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
  import { childrenHeading, newChildLabel, type LocationDetail } from './location-helpers';
  import LocationEditorSwitch from './edit/LocationEditorSwitch.svelte';

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

  const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
  let isMobile = $derived(isMobileFlag.current);
  let editing = $state<LocationEditSectionKey | null>(null);
  let visibleSections = $derived<LocationEditSectionDef[]>(
    locationEditSectionsFor(profile.location_type),
  );
  let syncEnabled = $derived(!isMobile);
  let lastUrlEditing = $state<LocationEditSectionKey | null>(null);

  function updateEditQuery(nextEditing: LocationEditSectionKey | null) {
    const current = page.url.searchParams.get('edit') ?? null;
    const desired = nextEditing ? (findLocationSectionByKey(nextEditing)?.segment ?? null) : null;
    if (current === desired) return;
    const url = new URL(page.url);
    if (desired) url.searchParams.set('edit', desired);
    else url.searchParams.delete('edit');
    goto(`${url.pathname}${url.search}`, { replaceState: true, noScroll: true, keepFocus: true });
  }

  function resolveEditingFromUrl(): LocationEditSectionKey | null {
    if (!syncEnabled) return null;
    const segment = page.url.searchParams.get('edit');
    const matched = segment ? findLocationSectionBySegment(segment) : undefined;
    if (!matched) return null;
    if (matched.countryOnly && profile.location_type !== 'country') return null;
    return matched.key;
  }

  $effect(() => {
    const nextEditing = resolveEditingFromUrl();
    lastUrlEditing = nextEditing;
    editing = nextEditing;
  });

  $effect(() => {
    if (!syncEnabled) return;
    if (editing === lastUrlEditing) return;
    lastUrlEditing = editing;
    updateEditQuery(editing);
  });

  let editMenuItems = $derived.by<EditSectionMenuItem[]>(() => {
    if (isRoot) {
      return [{ key: 'new', label: '+ New Country', href: resolveHref('/locations/new') }];
    }
    const childLabel = newChildLabel(profile);
    // Name, parent, slug, and location_type are intentionally absent —
    // see docs/plans/model_driven_metadata/LocationCrud.md §"Decisions".
    const items: EditSectionMenuItem[] = visibleSections.map((section) =>
      isMobile
        ? {
            key: section.key,
            label: section.label,
            href: resolveHref(`/locations/${path}/edit/${section.segment}`),
          }
        : {
            key: section.key,
            label: section.label,
            onclick: () => (editing = section.key),
          },
    );
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

{#if !isRoot}
  <SectionEditorHost
    bind:editingKey={editing}
    sections={visibleSections}
    switcherItems={editMenuItems}
  >
    {#snippet editor(key, { ref, onsaved, onerror, ondirtychange })}
      <LocationEditorSwitch
        sectionKey={key}
        initialData={profile}
        publicId={profile.location_path}
        bind:editorRef={ref.current}
        {onsaved}
        {onerror}
        {ondirtychange}
      />
    {/snippet}
  </SectionEditorHost>
{/if}

<style>
  .count {
    font-size: var(--font-size-0);
    color: var(--color-text-muted);
  }
</style>
