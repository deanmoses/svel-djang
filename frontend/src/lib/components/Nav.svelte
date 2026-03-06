<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { faBars, faMagnifyingGlass, faXmark } from '@fortawesome/free-solid-svg-icons';
	import FaIcon from './FaIcon.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';

	let mobileNavOpen = $state(false);

	const navItems = [
		{ href: '/titles' as const, label: 'Titles' },
		{ href: '/manufacturers' as const, label: 'Manufacturers' },
		{ href: '/people' as const, label: 'People' },
		{ href: '/api-docs' as const, label: 'API' }
	];

	function isActive(href: string) {
		return page.url.pathname.startsWith(href);
	}

	let toggleIcon = $derived(mobileNavOpen ? faXmark : faBars);
</script>

<header class="site-header">
	<div class="header-inner">
		<a href={resolve('/')} class="site-title">{SITE_NAME}</a>

		<nav class="site-nav" class:open={mobileNavOpen}>
			{#each navItems as { href, label } (href)}
				<a
					href={resolve(href)}
					class="nav-link"
					class:active={isActive(href)}
					onclick={() => (mobileNavOpen = false)}
				>
					{label}
				</a>
			{/each}
		</nav>

		<div class="header-actions">
			<a
				href={resolveHref('/search')}
				class="search-link"
				class:active={isActive('/search')}
				aria-label="Search"
			>
				<FaIcon icon={faMagnifyingGlass} />
			</a>

			<button
				class="mobile-toggle"
				onclick={() => (mobileNavOpen = !mobileNavOpen)}
				aria-label="Toggle navigation"
				aria-expanded={mobileNavOpen}
			>
				<FaIcon icon={toggleIcon} />
			</button>
		</div>
	</div>
</header>

<style>
	.site-header {
		background-color: var(--color-surface);
		border-bottom: 1px solid var(--color-border-soft);
		position: sticky;
		top: 0;
		z-index: 100;
	}

	.header-inner {
		max-width: 72rem;
		margin: 0 auto;
		padding: var(--size-3) var(--size-5);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.site-title {
		font-size: var(--font-size-4);
		font-weight: 700;
		color: var(--color-text-primary);
		text-decoration: none;
	}

	.site-title:hover {
		color: var(--color-accent);
	}

	.site-nav {
		display: flex;
		gap: var(--size-5);
	}

	.nav-link {
		color: var(--color-text-muted);
		text-decoration: none;
		font-size: var(--font-size-2);
		font-weight: 500;
		padding: var(--size-1) 0;
		border-bottom: 2px solid transparent;
		transition:
			color 0.15s var(--ease-2),
			border-color 0.15s var(--ease-2);
	}

	.nav-link:hover {
		color: var(--color-text-primary);
	}

	.nav-link.active {
		color: var(--color-accent);
		border-bottom-color: var(--color-accent);
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: var(--size-3);
	}

	.search-link {
		color: var(--color-text-muted);
		padding: var(--size-1);
		display: flex;
		align-items: center;
		transition: color 0.15s var(--ease-2);
	}

	.search-link:hover {
		color: var(--color-text-primary);
	}

	.search-link.active {
		color: var(--color-accent);
	}

	.search-link :global(svg) {
		width: 1.1rem;
		height: 1.1rem;
	}

	.mobile-toggle {
		display: none;
		background: none;
		border: none;
		color: var(--color-text-primary);
		cursor: pointer;
		padding: var(--size-1);
	}

	.mobile-toggle :global(svg) {
		width: 1.25rem;
		height: 1.25rem;
	}

	@media (max-width: 640px) {
		.mobile-toggle {
			display: block;
		}

		.site-nav {
			display: none;
			flex-direction: column;
			position: absolute;
			top: 100%;
			left: 0;
			right: 0;
			background-color: var(--color-surface);
			border-bottom: 1px solid var(--color-border-soft);
			padding: var(--size-3) var(--size-5);
			gap: var(--size-2);
		}

		.site-nav.open {
			display: flex;
		}
	}
</style>
