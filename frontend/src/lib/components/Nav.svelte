<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { faBars, faMagnifyingGlass, faXmark } from '@fortawesome/free-solid-svg-icons';
	import FaIcon from './FaIcon.svelte';
	import CoffeeStain from './effects/CoffeeStain.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
	import { auth } from '$lib/auth.svelte';

	let mobileNavOpen = $state(false);

	const navItems = [
		{ href: '/titles' as const, label: 'Titles' },
		{ href: '/manufacturers' as const, label: 'Manufacturers' },
		{ href: '/people' as const, label: 'People' },
		{ href: '/recent-changes' as const, label: 'Recent Changes' }
	];

	function isActive(href: string) {
		return page.url.pathname.startsWith(href);
	}

	let toggleIcon = $derived(mobileNavOpen ? faXmark : faBars);

	$effect(() => {
		auth.load();
	});

	async function handleLogout() {
		await auth.logout();
	}

	const randInt = (max: number) => Math.floor(Math.random() * max);

	// Stain seeds (one per stain strip)
	const stainSeed1 = randInt(1000);
	const stainSeed2 = randInt(1000);
	const stainSeed3 = randInt(1000);

	// Torn bottom edge
	const tornId = `tear-${crypto.randomUUID()}`;
	const tornSeed = randInt(1000);
</script>

<!-- Torn edge filter definition -->
<svg class="svg-filters" aria-hidden="true">
	<defs>
		<filter id={tornId} x="-2%" y="-2%" width="104%" height="120%">
			<feTurbulence
				type="turbulence"
				baseFrequency="0.06 0.02"
				numOctaves="4"
				seed={tornSeed}
				result="warp"
			/>
			<feDisplacementMap in="SourceGraphic" in2="warp" scale="6" yChannelSelector="R" />
		</filter>
	</defs>
</svg>

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
				<FaIcon icon={faMagnifyingGlass} size="1.1rem" />
			</a>

			{#if auth.loaded}
				{#if auth.isAuthenticated}
					<a href={resolveHref(`/users/${auth.username}`)} class="auth-user">{auth.username}</a>
					<button class="auth-link" onclick={handleLogout}>Sign out</button>
				{:else}
					<a
						href={`/api/auth/login/?next=${encodeURIComponent(page.url.pathname)}`}
						class="auth-link">Sign in</a
					>
				{/if}
			{/if}

			<button
				class="mobile-toggle"
				onclick={() => (mobileNavOpen = !mobileNavOpen)}
				aria-label="Toggle navigation"
				aria-expanded={mobileNavOpen}
			>
				<FaIcon icon={toggleIcon} size="1.25rem" />
			</button>
		</div>
	</div>

	<!-- Coffee stain overlays — three strips covering full width -->
	<div class="header-stains">
		<CoffeeStain
			seed={stainSeed1}
			frequency={0.03}
			opacity={0.12}
			blur={4}
			threshold="0 0 0 0 0 0 0.5 0.7"
			x="0%"
			width="40%"
		/>
		<CoffeeStain
			seed={stainSeed2}
			frequency={0.04}
			octaves={4}
			opacity={0.08}
			blur={5}
			threshold="0 0 0 0 0 0 0 0.4"
			color="rgb(100, 65, 20)"
			x="30%"
			width="40%"
		/>
		<CoffeeStain
			seed={stainSeed3}
			frequency={0.025}
			opacity={0.1}
			blur={3}
			threshold="0 0 0 0 0 0.4 0.6 0.8"
			color="rgb(130, 90, 35)"
			x="60%"
			width="40%"
		/>
	</div>

	<!-- Torn bottom edge -->
	<div class="torn-edge" style:filter="url(#{tornId})"></div>
</header>

<style>
	.svg-filters {
		position: absolute;
		width: 0;
		height: 0;
		overflow: hidden;
		pointer-events: none;
	}

	.site-header {
		/* Color tokens — overridden in dark mode */
		--header-bg: #efe8dc;
		--header-ink: #3d3529;
		--header-ink-muted: #6b5d4d;

		position: sticky;
		top: 0;
		z-index: 100;
		background-color: var(--header-bg);
		border-bottom: none;
	}

	/* Subtle paper grain via repeating gradient */
	.site-header::before {
		content: '';
		position: absolute;
		inset: 0;
		background: repeating-linear-gradient(
			0deg,
			transparent,
			transparent 2px,
			rgba(0, 0, 0, 0.01) 2px,
			rgba(0, 0, 0, 0.01) 4px
		);
		pointer-events: none;
		z-index: 1;
	}

	/* Torn paper bottom edge — shares background color via token */
	.torn-edge {
		position: absolute;
		bottom: -4px;
		left: 0;
		right: 0;
		height: 8px;
		background: var(--header-bg);
		pointer-events: none;
		z-index: 3;
	}

	.header-inner {
		position: relative;
		max-width: 72rem;
		margin: 0 auto;
		padding: var(--size-3) var(--size-5);
		display: flex;
		align-items: center;
		justify-content: space-between;
		z-index: 10;
	}

	.site-title {
		font-size: var(--font-size-4);
		font-weight: 700;
		color: var(--header-ink);
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
		color: var(--header-ink-muted);
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
		color: var(--header-ink);
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
		color: var(--header-ink-muted);
		padding: var(--size-1);
		display: flex;
		align-items: center;
		transition: color 0.15s var(--ease-2);
	}

	.search-link:hover {
		color: var(--header-ink);
	}

	.search-link.active {
		color: var(--color-accent);
	}

	.auth-user {
		font-size: var(--font-size-2);
		color: var(--header-ink-muted);
		text-decoration: none;
		transition: color 0.15s var(--ease-2);
	}

	.auth-user:hover {
		color: var(--header-ink);
	}

	.auth-link {
		font-size: var(--font-size-2);
		color: var(--header-ink-muted);
		text-decoration: none;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		font-weight: 500;
		transition: color 0.15s var(--ease-2);
	}

	.auth-link:hover {
		color: var(--header-ink);
	}

	.mobile-toggle {
		display: none;
		background: none;
		border: none;
		color: var(--header-ink);
		cursor: pointer;
		padding: var(--size-1);
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
			background-color: var(--header-bg);
			border-bottom: 1px solid rgba(0, 0, 0, 0.08);
			padding: var(--size-3) var(--size-5);
			gap: var(--size-2);
		}

		.site-nav.open {
			display: flex;
		}
	}

	.header-stains {
		display: none;
		position: absolute;
		inset: 0;
		pointer-events: none;
	}

	@media (prefers-color-scheme: light) {
		.header-stains {
			display: block;
		}
	}

	/* ---- Dark mode ---- */
	@media (prefers-color-scheme: dark) {
		.site-header {
			--header-bg: #26221d;
			--header-ink: var(--color-text-primary);
			--header-ink-muted: var(--color-text-muted);
		}

		.site-header::before {
			background: none;
		}

		@media (max-width: 640px) {
			.site-nav {
				border-bottom-color: var(--color-border-soft);
			}
		}
	}
</style>
