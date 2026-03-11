<script lang="ts">
	import { resolveHref } from '$lib/utils';

	type Crumb = { label: string; href: string };

	let { crumbs, current }: { crumbs: Crumb[]; current: string } = $props();
</script>

<nav aria-label="Breadcrumb" class="breadcrumb">
	<ol>
		{#each crumbs as crumb (crumb.href)}
			<li>
				<a href={resolveHref(crumb.href)}>{crumb.label}</a>
			</li>
		{/each}
		<li aria-current="page">{current}</li>
	</ol>
</nav>

<style>
	ol {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		list-style: none;
		padding: 0;
		margin: 0;
		gap: var(--size-1);
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	li:not(:last-child)::after {
		content: '/';
		margin-left: var(--size-1);
		color: var(--color-text-muted);
	}

	a {
		color: var(--color-text-muted);
		text-decoration: none;
	}

	a:hover {
		color: var(--color-text-primary);
		text-decoration: underline;
	}

	li[aria-current='page'] {
		color: var(--color-text-primary);
	}
</style>
