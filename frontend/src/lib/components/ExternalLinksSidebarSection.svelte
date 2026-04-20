<script lang="ts">
	import SidebarSection from './SidebarSection.svelte';

	let {
		ipdbId,
		opdbId,
		pinsideId,
		note = 'See this on other sites:',
		onEdit = undefined
	}: {
		ipdbId?: number | null;
		opdbId?: string | null;
		pinsideId?: number | null;
		note?: string;
		onEdit?: (() => void) | undefined;
	} = $props();
</script>

{#if ipdbId || opdbId || pinsideId}
	<SidebarSection heading="External Links" {note} {onEdit}>
		<div class="external-ids">
			{#if ipdbId}
				<a href="https://www.ipdb.org/machine.cgi?id={ipdbId}"> Internet Pinball Database </a>
			{/if}
			{#if opdbId}
				<a href="https://opdb.org/machines/{opdbId}">Open Pinball Database</a>
			{/if}
			{#if pinsideId}
				<a href="https://pinside.com/pinball/machine/{pinsideId}">Pinside</a>
			{/if}
		</div>
	</SidebarSection>
{/if}

<style>
	.external-ids {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-3);
		font-size: var(--font-size-0);
	}
</style>
