<script lang="ts">
	let {
		name,
		heroImageUrl = null,
		heroImageAlt = '',
		parentLink = null,
		metaItems = []
	}: {
		name: string;
		heroImageUrl?: string | null;
		heroImageAlt?: string;
		parentLink?: { text: string; href: string } | null;
		metaItems?: Array<{ text: string; href?: string }>;
	} = $props();
</script>

{#snippet content()}
	{#if parentLink}
		<a class="kicker" href={parentLink.href}>{parentLink.text}</a>
	{/if}
	<h1>{name}</h1>
	{#if metaItems.length > 0}
		<div class="meta">
			{#each metaItems as item, i (i)}
				<span>
					{#if item.href}
						<a href={item.href}>{item.text}</a>
					{:else}
						{item.text}
					{/if}
				</span>
			{/each}
		</div>
	{/if}
{/snippet}

{#if heroImageUrl}
	<div class="hero-banner">
		<img class="hero-bg" src={heroImageUrl} alt={heroImageAlt} />
		<div class="hero-scrim"></div>
		<header class="hero-header">
			{@render content()}
		</header>
	</div>
{:else}
	<header>
		{@render content()}
	</header>
{/if}

<style>
	/* Kicker / parent link */
	.kicker {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		text-decoration: none;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.kicker:hover {
		color: var(--color-accent);
	}

	/* Heading */
	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	/* Meta */
	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-2);
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
	}

	.meta span:not(:last-child)::after {
		content: '·';
		margin-left: var(--size-2);
	}

	/* Plain header (no image) */
	header {
		margin-bottom: var(--size-2);
	}

	/* Hero banner with overlaid text */
	.hero-banner {
		position: relative;
		overflow: hidden;
		border-radius: var(--radius-3);
		min-height: 14rem;
		max-height: 22rem;
		margin-bottom: var(--size-5);
		display: flex;
		align-items: flex-end;
		background-color: var(--color-surface);
	}

	.hero-bg {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: center 20%;
		z-index: 0;
	}

	.hero-scrim {
		position: absolute;
		inset: 0;
		z-index: 1;
		background: linear-gradient(
			to top,
			rgba(0, 0, 0, 0.85) 0%,
			rgba(0, 0, 0, 0.5) 40%,
			rgba(0, 0, 0, 0.1) 70%,
			transparent 100%
		);
		pointer-events: none;
	}

	.hero-header {
		position: relative;
		z-index: 2;
		padding: var(--size-5) var(--size-5) var(--size-4);
		width: 100%;
		margin-bottom: 0;
	}

	/* Hero overrides — light-on-dark text */
	.hero-header .kicker {
		color: rgba(255, 255, 255, 0.7);
	}

	.hero-header .kicker:hover {
		color: #ffffff;
	}

	.hero-header h1 {
		color: #ffffff;
		text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
	}

	.hero-header .meta {
		color: rgba(255, 255, 255, 0.85);
	}

	.hero-header .meta a {
		color: rgba(255, 255, 255, 0.9);
		text-decoration: underline;
		text-decoration-color: rgba(255, 255, 255, 0.4);
	}

	.hero-header .meta a:hover {
		color: #ffffff;
		text-decoration-color: #ffffff;
	}

	.hero-header .meta span:not(:last-child)::after {
		color: rgba(255, 255, 255, 0.5);
	}

	/* Responsive */
	@media (max-width: 40rem) {
		.hero-banner {
			min-height: 10rem;
			max-height: 16rem;
			border-radius: 0;
			margin-left: calc(-1 * var(--size-5));
			margin-right: calc(-1 * var(--size-5));
		}

		.hero-header {
			padding: var(--size-3) var(--size-4) var(--size-3);
		}

		.hero-header h1 {
			font-size: var(--font-size-5);
		}

		.hero-header .meta {
			font-size: var(--font-size-0);
		}
	}
</style>
