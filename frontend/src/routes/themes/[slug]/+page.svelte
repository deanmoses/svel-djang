<script lang="ts">
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import HierarchicalTaxonomyChildrenAccordion from '$lib/components/HierarchicalTaxonomyChildrenAccordion.svelte';
	import HierarchicalTaxonomyMobileMetaBar from '$lib/components/HierarchicalTaxonomyMobileMetaBar.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import Markdown from '$lib/components/Markdown.svelte';

	let { data } = $props();
	let theme = $derived(data.theme);

	// Themes has historically shown aliases verbatim (no near-duplicate filter
	// against the canonical name). Preserve that.
	let aliases = $derived(theme.aliases ?? []);
	let childHeading = $derived(`Sub-themes (${theme.children?.length ?? 0})`);
</script>

{#if theme.description?.html}
	<section class="description">
		<Markdown html={theme.description.html} citations={theme.description.citations ?? []} />
		<AttributionLine attribution={theme.description.attribution} />
	</section>
{/if}

<HierarchicalTaxonomyMobileMetaBar
	basePath="/themes"
	parents={theme.parents ?? []}
	{aliases}
	parentLabel="Parent themes"
/>

<HierarchicalTaxonomyChildrenAccordion
	basePath="/themes"
	children={theme.children ?? []}
	heading={childHeading}
/>

{#if theme.machines.length === 0}
	<p class="empty">No machines with this theme.</p>
{:else}
	<ClientFilteredGrid items={theme.machines} showCount={false}>
		{#snippet children(machine)}
			<MachineCard
				slug={machine.slug}
				name={machine.name}
				thumbnailUrl={machine.thumbnail_url}
				manufacturerName={machine.manufacturer?.name}
				year={machine.year}
			/>
		{/snippet}
	</ClientFilteredGrid>
{/if}

<style>
	.description {
		margin-bottom: var(--size-6);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}
</style>
