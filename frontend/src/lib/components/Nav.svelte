<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { goto } from '$app/navigation';
	import { faBars, faMagnifyingGlass, faXmark } from '@fortawesome/free-solid-svg-icons';
	import FaIcon from './FaIcon.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
	import { auth } from '$lib/auth.svelte';

	let mobileNavOpen = $state(false);

	const navItems = [
		{ href: '/titles' as const, label: 'Titles' },
		{ href: '/manufacturers' as const, label: 'Manufacturers' },
		{ href: '/people' as const, label: 'People' }
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
		await goto(resolveHref('/'));
	}

	// Unique ID for SVG filter references
	const uid = Math.random().toString(36).slice(2, 8);

	// Random seeds for stain patterns
	const stainSeed1 = Math.floor(Math.random() * 1000);
	const stainSeed2 = Math.floor(Math.random() * 1000);
	const stainSeed3 = Math.floor(Math.random() * 1000);

	// Stain positions (spread across the header width)
	const stain1X = 5 + Math.random() * 25;
	const stain1Y = 10 + Math.random() * 80;
	const stain2X = 40 + Math.random() * 20;
	const stain2Y = 10 + Math.random() * 80;
	const stain3X = 70 + Math.random() * 25;
	const stain3Y = 10 + Math.random() * 80;

	// Torn edge: a random jagged bottom border
	const tornSeed = Math.floor(Math.random() * 1000);
</script>

<!-- Hidden SVG filter definitions -->
<svg class="svg-filters" aria-hidden="true">
	<defs>
		<!-- Stain filters with different seeds -->
		<filter id="hdr-stain1-{uid}" x="-50%" y="-50%" width="200%" height="200%">
			<feTurbulence
				type="fractalNoise"
				baseFrequency="0.03"
				numOctaves="5"
				seed={stainSeed1}
				result="noise"
			/>
			<feComponentTransfer in="noise" result="blobs">
				<feFuncA type="discrete" tableValues="0 0 0 0 0 0 0.5 0.7" />
			</feComponentTransfer>
			<feFlood flood-color="rgb(120, 80, 30)" flood-opacity="0.12" result="color" />
			<feComposite in="color" in2="blobs" operator="in" result="stain" />
			<feGaussianBlur in="stain" stdDeviation="4" />
		</filter>

		<filter id="hdr-stain2-{uid}" x="-50%" y="-50%" width="200%" height="200%">
			<feTurbulence
				type="fractalNoise"
				baseFrequency="0.04"
				numOctaves="4"
				seed={stainSeed2}
				result="noise"
			/>
			<feComponentTransfer in="noise" result="blobs">
				<feFuncA type="discrete" tableValues="0 0 0 0 0 0 0 0.4" />
			</feComponentTransfer>
			<feFlood flood-color="rgb(100, 65, 20)" flood-opacity="0.08" result="color" />
			<feComposite in="color" in2="blobs" operator="in" result="stain" />
			<feGaussianBlur in="stain" stdDeviation="5" />
		</filter>

		<filter id="hdr-stain3-{uid}" x="-50%" y="-50%" width="200%" height="200%">
			<feTurbulence
				type="fractalNoise"
				baseFrequency="0.025"
				numOctaves="5"
				seed={stainSeed3}
				result="noise"
			/>
			<feComponentTransfer in="noise" result="blobs">
				<feFuncA type="discrete" tableValues="0 0 0 0 0 0.4 0.6 0.8" />
			</feComponentTransfer>
			<feFlood flood-color="rgb(130, 90, 35)" flood-opacity="0.1" result="color" />
			<feComposite in="color" in2="blobs" operator="in" result="stain" />
			<feGaussianBlur in="stain" stdDeviation="3" />
		</filter>

		<!-- Torn bottom edge displacement -->
		<filter id="hdr-tear-{uid}" x="-2%" y="-2%" width="104%" height="120%">
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
				<FaIcon icon={faMagnifyingGlass} />
			</a>

			{#if auth.loaded}
				{#if auth.isAuthenticated}
					<span class="auth-user">{auth.username}</span>
					<button class="auth-link" onclick={handleLogout}>Sign out</button>
				{:else}
					<a href={resolveHref('/login')} class="auth-link">Sign in</a>
				{/if}
			{/if}

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

	<!-- Coffee stain overlays -->
	<svg class="stain-overlay" aria-hidden="true">
		<rect
			x="{stain1X}%"
			y="{stain1Y}%"
			width="20%"
			height="80%"
			filter="url(#{`hdr-stain1-${uid}`})"
		/>
		<rect
			x="{stain2X}%"
			y="{stain2Y}%"
			width="15%"
			height="70%"
			filter="url(#{`hdr-stain2-${uid}`})"
		/>
		<rect
			x="{stain3X}%"
			y="{stain3Y}%"
			width="18%"
			height="75%"
			filter="url(#{`hdr-stain3-${uid}`})"
		/>
	</svg>

	<!-- Torn bottom edge -->
	<div class="torn-edge" style:filter="url(#{`hdr-tear-${uid}`})"></div>
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
		position: sticky;
		top: 0;
		z-index: 100;
		background-color: #efe8dc;
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

	.stain-overlay {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		z-index: 2;
		overflow: hidden;
	}

	/* Torn paper bottom edge — a strip that gets displaced by SVG turbulence */
	.torn-edge {
		position: absolute;
		bottom: -4px;
		left: 0;
		right: 0;
		height: 8px;
		background: #efe8dc;
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
		color: #3d3529;
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
		color: #6b5d4d;
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
		color: #3d3529;
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
		color: #6b5d4d;
		padding: var(--size-1);
		display: flex;
		align-items: center;
		transition: color 0.15s var(--ease-2);
	}

	.search-link:hover {
		color: #3d3529;
	}

	.search-link.active {
		color: var(--color-accent);
	}

	.search-link :global(svg) {
		width: 1.1rem;
		height: 1.1rem;
	}

	.auth-user {
		font-size: var(--font-size-2);
		color: #6b5d4d;
	}

	.auth-link {
		font-size: var(--font-size-2);
		color: #6b5d4d;
		text-decoration: none;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		font-weight: 500;
		transition: color 0.15s var(--ease-2);
	}

	.auth-link:hover {
		color: #3d3529;
	}

	.mobile-toggle {
		display: none;
		background: none;
		border: none;
		color: #3d3529;
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
			background-color: #efe8dc;
			border-bottom: 1px solid rgba(0, 0, 0, 0.08);
			padding: var(--size-3) var(--size-5);
			gap: var(--size-2);
		}

		.site-nav.open {
			display: flex;
		}
	}

	/* ---- Dark mode ---- */
	@media (prefers-color-scheme: dark) {
		.site-header {
			background-color: var(--color-surface);
		}

		.site-header::before {
			background: none;
		}

		.torn-edge {
			background: var(--color-surface);
		}

		.site-title {
			color: var(--color-text-primary);
		}

		.nav-link {
			color: var(--color-text-muted);
		}

		.nav-link:hover {
			color: var(--color-text-primary);
		}

		.search-link {
			color: var(--color-text-muted);
		}

		.search-link:hover {
			color: var(--color-text-primary);
		}

		.auth-user {
			color: var(--color-text-muted);
		}

		.auth-link {
			color: var(--color-text-muted);
		}

		.auth-link:hover {
			color: var(--color-text-primary);
		}

		.mobile-toggle {
			color: var(--color-text-primary);
		}

		@media (max-width: 640px) {
			.site-nav {
				background-color: var(--color-surface);
				border-bottom-color: var(--color-border-soft);
			}
		}
	}
</style>
