<script lang="ts">
	import { resolve } from '$app/paths';

	interface Variant {
		name: string;
		slug: string;
		year?: number | null;
	}

	interface Model {
		name: string;
		slug: string;
		year?: number | null;
		variants: Variant[];
	}

	let {
		models,
		heading = 'Models',
		currentSlug = undefined,
		aliasOfSlug = undefined,
		excludeSlug = undefined
	}: {
		models: Model[];
		heading?: string;
		currentSlug?: string;
		aliasOfSlug?: string;
		excludeSlug?: string;
	} = $props();

	function sortedVariants(variants: Variant[]): Variant[] {
		return [...variants].sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
	}

	let filteredModels = $derived(
		excludeSlug ? models.filter((m) => m.slug !== excludeSlug) : models
	);
</script>

{#if filteredModels.length > 0}
	<section class="sidebar-section">
		<h3>{heading}</h3>
		<ul class="sidebar-list">
			{#each filteredModels as parent (parent.slug)}
				<li
					class:current={currentSlug !== undefined &&
						(parent.slug === currentSlug || parent.slug === aliasOfSlug)}
				>
					<a href={resolve(`/models/${parent.slug}`)}>{parent.name}</a>
					{#if parent.year}
						<span class="muted">{parent.year}</span>
					{/if}
				</li>
				{#each sortedVariants(parent.variants) as variant (variant.slug)}
					<li
						class="variant-indent"
						class:current={currentSlug !== undefined && variant.slug === currentSlug}
					>
						<a href={resolve(`/models/${variant.slug}`)}>{variant.name}</a>
						{#if variant.year}
							<span class="muted">{variant.year}</span>
						{/if}
					</li>
				{/each}
			{/each}
		</ul>
	</section>
{/if}

<style>
	.sidebar-section {
		padding-bottom: var(--size-3);
		border-bottom: 1px solid var(--color-border-soft);
	}

	.sidebar-section h3 {
		font-size: var(--font-size-1);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-1);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.sidebar-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.sidebar-list li {
		display: flex;
		align-items: baseline;
		padding: var(--size-1) 0;
		font-size: var(--font-size-0);
	}

	.sidebar-list li > a {
		flex: 1;
	}

	.sidebar-list li:not(:last-child):not(.variant-indent):not(:has(+ .variant-indent)) {
		border-bottom: 1px solid var(--color-border-soft);
	}

	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.variant-indent {
		margin-left: var(--size-4);
	}

	.variant-indent::before {
		content: '└';
		margin-right: var(--size-2);
		color: var(--color-text-muted);
	}

	.current > a {
		font-weight: 600;
		color: var(--color-accent);
	}
</style>
