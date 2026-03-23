<script lang="ts">
	import { resolve } from '$app/paths';
	import type { components } from '$lib/api/schema';

	type Model = components['schemas']['MachineModelDetailSchema'];

	let { model }: { model: Model } = $props();
</script>

<dl>
	{#if model.technology_generation_slug}
		<dt>Generation</dt>
		<dd>
			<a href={resolve(`/technology-generations/${model.technology_generation_slug}`)}
				>{model.technology_generation_name}</a
			>
		</dd>
	{/if}
	{#if model.technology_subgeneration_slug}
		<dt>Subgeneration</dt>
		<dd>
			<a href={resolve(`/technology-subgenerations/${model.technology_subgeneration_slug}`)}
				>{model.technology_subgeneration_name}</a
			>
		</dd>
	{/if}
	{#if model.display_type_slug}
		<dt>Display Type</dt>
		<dd>
			<a href={resolve(`/display-types/${model.display_type_slug}`)}>{model.display_type_name}</a>
		</dd>
	{/if}
	{#if model.player_count}
		<dt>Players</dt>
		<dd>{model.player_count}</dd>
	{/if}
	{#if model.flipper_count}
		<dt>Flippers</dt>
		<dd>{model.flipper_count}</dd>
	{/if}
	{#if model.production_quantity}
		<dt>Units Made</dt>
		<dd>{model.production_quantity}</dd>
	{/if}
	{#if model.system_slug}
		<dt>System</dt>
		<dd>
			<a href={resolve(`/systems/${model.system_slug}`)}>{model.system_name}</a>
		</dd>
	{/if}
	{#if model.themes.length > 0}
		<dt>Themes</dt>
		<dd>
			{#each model.themes as theme, i (theme.slug)}
				{#if i > 0},{/if}
				<a href={resolve(`/themes/${theme.slug}`)}>{theme.name}</a>
			{/each}
		</dd>
	{/if}
	{#if model.franchise}
		<dt>Franchise</dt>
		<dd>
			<a href={resolve(`/franchises/${model.franchise.slug}`)}>{model.franchise.name}</a>
		</dd>
	{/if}
	{#if model.abbreviations.length > 0}
		<dt>Abbrs</dt>
		<dd>{model.abbreviations.join(', ')}</dd>
	{/if}
	{#if model.cabinet_slug}
		<dt>Cabinet</dt>
		<dd>
			<a href={resolve(`/cabinets/${model.cabinet_slug}`)}>{model.cabinet_name}</a>
		</dd>
	{/if}
	{#if model.game_format_slug}
		<dt>Format</dt>
		<dd>
			<a href={resolve(`/game-formats/${model.game_format_slug}`)}>{model.game_format_name}</a>
		</dd>
	{/if}
	{#if model.display_subtype_slug}
		<dt>Display</dt>
		<dd>
			<a href={resolve(`/display-subtypes/${model.display_subtype_slug}`)}
				>{model.display_subtype_name}</a
			>
		</dd>
	{/if}
	{#if model.gameplay_features.length > 0}
		<dt>Features</dt>
		<dd>
			{#each model.gameplay_features as feature, i (feature.slug)}
				{#if i > 0},{/if}
				<a href={resolve(`/gameplay-features/${feature.slug}`)}>{feature.name}</a
				>{#if feature.count}&nbsp;({feature.count}){/if}
			{/each}
		</dd>
	{/if}
	{#if model.reward_types && model.reward_types.length > 0}
		<dt>Reward Types</dt>
		<dd>
			{#each model.reward_types as rt, i (rt.slug)}
				{#if i > 0},{/if}
				<a href={resolve(`/reward-types/${rt.slug}`)}>{rt.name}</a>
			{/each}
		</dd>
	{/if}
	{#if model.variant_features.length > 0}
		<dt>Variant</dt>
		<dd>{model.variant_features.join(', ')}</dd>
	{/if}
	{#if model.series.length > 0}
		<dt>Series</dt>
		<dd>
			{#each model.series as s, i (s.slug)}
				{#if i > 0},{/if}
				<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
			{/each}
		</dd>
	{/if}
</dl>

<style>
	dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0 var(--size-3);
		align-items: baseline;
	}

	dt,
	dd {
		font-size: var(--font-size-0);
		margin: 0;
		padding: 2px 0;
	}

	dt {
		color: var(--color-text-muted);
		font-weight: 500;
	}

	dd {
		color: var(--color-text-primary);
	}
</style>
