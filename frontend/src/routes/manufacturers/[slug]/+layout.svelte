<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { formatYearRange, resolveHref, websiteHostname } from '$lib/utils';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import { auth } from '$lib/auth.svelte';
	import ExpandableSidebarList from '$lib/components/ExpandableSidebarList.svelte';
	import LocationLink from '$lib/components/LocationLink.svelte';
	import PageActionBar from '$lib/components/PageActionBar.svelte';
	import RecordDetailShell from '$lib/components/RecordDetailShell.svelte';
	import SectionEditorHost from '$lib/components/SectionEditorHost.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import { getMenuItemAction, type EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import { manufacturerEditActionContext } from '$lib/components/editors/edit-action-context';
	import {
		findManufacturerSectionByKey,
		findManufacturerSectionBySegment,
		MANUFACTURER_EDIT_SECTIONS,
		type ManufacturerEditSectionKey
	} from '$lib/components/editors/manufacturer-edit-sections';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { resolveDetailSubrouteMode } from '$lib/detail-subroute-mode';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
	import ManufacturerEditorSwitch from './edit/ManufacturerEditorSwitch.svelte';

	let { data, children } = $props();
	let mfr = $derived(data.manufacturer);
	let slug = $derived(page.params.slug);

	let yearsActive = $derived(formatYearRange(mfr.year_start, mfr.year_end));
	let metaDescription = $derived(mfr.description?.text || `${mfr.name} — pinball manufacturer`);
	let mode = $derived(resolveDetailSubrouteMode(page.url.pathname));
	let isDetail = $derived(mode === 'detail');
	let isEdit = $derived(mode === 'edit');
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
	let isMobile = $derived(isMobileFlag.current);
	let editing = $state<ManufacturerEditSectionKey | null>(null);
	let syncEnabled = $derived(!isMobile && !isEdit);
	// Tracks the last URL-derived edit section so local modal state doesn't immediately write it back.
	let lastUrlEditing = $state<ManufacturerEditSectionKey | null>(null);

	$effect(() => {
		auth.load();
	});

	function updateEditQuery(nextEditing: ManufacturerEditSectionKey | null) {
		const current = page.url.searchParams.get('edit') ?? null;
		const desired = nextEditing
			? (findManufacturerSectionByKey(nextEditing)?.segment ?? null)
			: null;
		if (current === desired) return;
		const url = new URL(page.url);
		if (desired) url.searchParams.set('edit', desired);
		else url.searchParams.delete('edit');
		goto(`${url.pathname}${url.search}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	function resolveEditingFromUrl(): ManufacturerEditSectionKey | null {
		if (!syncEnabled) return null;
		const section = page.url.searchParams.get('edit');
		const matched = section ? findManufacturerSectionBySegment(section) : undefined;
		return matched?.key ?? null;
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

	let hasEntityLocations = $derived(mfr.entities.some((entity) => entity.locations.length > 0));
	let metaItems = $derived(yearsActive ? [{ text: yearsActive }] : []);
	let editSections: EditSectionMenuItem[] = $derived(
		MANUFACTURER_EDIT_SECTIONS.map((section) =>
			isMobile
				? {
						key: section.key,
						label: section.label,
						href: resolve(`/manufacturers/${slug}/edit/${section.segment}`)
					}
				: {
						key: section.key,
						label: section.label,
						onclick: () => (editing = section.key)
					}
		)
	);

	function editAction(sectionKey: ManufacturerEditSectionKey): (() => void) | undefined {
		if (!auth.isAuthenticated) return undefined;
		return getMenuItemAction(editSections, sectionKey, (href) => goto(href));
	}

	manufacturerEditActionContext.set(editAction);
</script>

<MetaTags
	title={mfr.name}
	description={metaDescription}
	url={page.url.href}
	image={mfr.logo_url}
	imageAlt={mfr.logo_url ? `${mfr.name} logo` : undefined}
/>

{#if isEdit}
	{@render children()}
{:else}
	{#snippet actionBar()}
		<PageActionBar
			detailHref={isDetail ? undefined : resolve(`/manufacturers/${slug}`)}
			editSections={auth.isAuthenticated ? editSections : undefined}
			historyHref={resolve(`/manufacturers/${slug}/edit-history`)}
			sourcesHref={resolve(`/manufacturers/${slug}/sources`)}
		/>
	{/snippet}

	{#snippet main()}
		{@render children()}
	{/snippet}

	{#snippet sidebar()}
		{#if mfr.logo_url}
			<div class="logo">
				<img src={mfr.logo_url} alt="{mfr.name} logo" />
			</div>
		{/if}

		{#if yearsActive}
			<SidebarSection heading="Years Active">
				<p class="sidebar-value">{yearsActive}</p>
			</SidebarSection>
		{/if}

		{#if mfr.entities.length > 0}
			<SidebarSection heading="Companies">
				<SidebarList>
					{#each mfr.entities as entity (entity.slug)}
						<SidebarListItem>
							<div class="entity">
								<a href={resolve(`/corporate-entities/${entity.slug}`)} class="entity-name"
									>{entity.name}</a
								>
								{#if formatYearRange(entity.year_start, entity.year_end)}
									<span class="muted">
										{formatYearRange(entity.year_start, entity.year_end)}
									</span>
								{/if}
								{#each entity.locations as loc, i (i)}
									<LocationLink {loc} />
								{/each}
							</div>
						</SidebarListItem>
					{/each}
				</SidebarList>
			</SidebarSection>
		{/if}

		{#if !hasEntityLocations && (mfr.headquarters || mfr.country)}
			<SidebarSection heading="Location">
				<p class="sidebar-value">
					{[mfr.headquarters, mfr.country].filter(Boolean).join(', ')}
				</p>
			</SidebarSection>
		{/if}

		{#if mfr.systems.length > 0}
			<SidebarSection heading="Systems">
				<SidebarList>
					{#each mfr.systems as system (system.slug)}
						<SidebarListItem>
							<a href={resolve(`/systems/${system.slug}`)}>{system.name}</a>
						</SidebarListItem>
					{/each}
				</SidebarList>
			</SidebarSection>
		{/if}

		{#if mfr.persons.length > 0}
			<SidebarSection heading="Notable People">
				<ExpandableSidebarList items={mfr.persons} limit={10} key={(person) => person.slug}>
					{#snippet children(person)}
						<SidebarListItem>
							<a href={resolveHref(`/people/${person.slug}`)}>{person.name}</a>
							{#if person.roles.length > 0}
								<span class="muted">{person.roles.join(', ')}</span>
							{/if}
						</SidebarListItem>
					{/snippet}
				</ExpandableSidebarList>
			</SidebarSection>
		{/if}

		{#if mfr.website}
			<SidebarSection heading="Links" onEdit={editAction('basics')}>
				<SidebarList>
					<SidebarListItem>
						<a href={mfr.website} target="_blank" rel="noopener">{websiteHostname(mfr.website)}</a>
					</SidebarListItem>
				</SidebarList>
			</SidebarSection>
		{/if}
	{/snippet}

	<RecordDetailShell
		name={mfr.name}
		{metaItems}
		sidebarDesktopOnly={isDetail}
		{actionBar}
		{main}
		{sidebar}
	/>

	<SectionEditorHost
		bind:editingKey={editing}
		sections={MANUFACTURER_EDIT_SECTIONS}
		switcherItems={editSections}
	>
		{#snippet editor(key, { ref, onsaved, onerror, ondirtychange })}
			<ManufacturerEditorSwitch
				sectionKey={key}
				initialData={mfr}
				slug={mfr.slug}
				bind:editorRef={ref.current}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{/snippet}
	</SectionEditorHost>
{/if}

<style>
	.logo {
		padding-bottom: var(--size-3);
		border-bottom: 1px solid var(--color-border-soft);
	}

	.logo img {
		max-width: 100%;
		max-height: 120px;
		object-fit: contain;
		display: block;
	}

	.entity {
		display: flex;
		flex-direction: column;
		gap: var(--size-00);
	}

	.entity-name {
		font-weight: 500;
		color: var(--color-text-primary);
		text-decoration: none;
	}

	.entity-name:hover {
		color: var(--color-accent);
	}

	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.sidebar-value {
		font-size: var(--font-size-1);
		color: var(--color-text-primary);
		margin: 0;
	}
</style>
