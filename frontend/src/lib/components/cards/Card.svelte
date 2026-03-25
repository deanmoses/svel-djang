<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { Action } from 'svelte/action';

	let {
		href,
		title,
		thumbnailUrl = null,
		children = undefined
	}: {
		href: string;
		title: string;
		thumbnailUrl?: string | null;
		children?: Snippet;
	} = $props();

	/**
	 * Svelte action that assigns random CSS custom properties to each card,
	 * giving every polaroid a unique aged/worn appearance.
	 */
	const polaroid: Action = (node) => {
		const rand = (min: number, max: number) => Math.random() * (max - min) + min;

		// Slight random rotation for that pinned-to-a-board feel
		node.style.setProperty('--rotation', `${rand(-3, 3)}deg`);

		// Faded photo: randomize sepia/brightness/contrast
		node.style.setProperty('--sepia', `${rand(0.3, 0.7)}`);
		node.style.setProperty('--brightness', `${rand(0.9, 1.05)}`);
		node.style.setProperty('--contrast', `${rand(0.85, 0.95)}`);
		node.style.setProperty('--saturate', `${rand(0.6, 0.85)}`);

		// Coffee stain: randomize position, size, and opacity
		node.style.setProperty('--stain-x', `${rand(15, 85)}%`);
		node.style.setProperty('--stain-y', `${rand(15, 85)}%`);
		node.style.setProperty('--stain-size', `${rand(3, 7)}rem`);
		node.style.setProperty('--stain-opacity', `${rand(0.06, 0.18)}`);

		// Second, subtler stain for realism
		node.style.setProperty('--stain2-x', `${rand(10, 90)}%`);
		node.style.setProperty('--stain2-y', `${rand(10, 90)}%`);
		node.style.setProperty('--stain2-size', `${rand(2, 5)}rem`);
		node.style.setProperty('--stain2-opacity', `${rand(0.03, 0.1)}`);

		// Yellowed paper tint intensity
		node.style.setProperty('--paper-yellow', `${rand(0.03, 0.08)}`);
	};
</script>

<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- href is pre-resolved by caller -->
<a {href} class="card" use:polaroid>
	<div class="card-photo">
		{#if thumbnailUrl}
			<img src={thumbnailUrl} alt="" class="card-img" loading="lazy" />
		{:else}
			<div class="card-img-placeholder"></div>
		{/if}
	</div>
	<div class="card-body">
		<h3 class="card-title">{title}</h3>
		{#if children}
			{@render children()}
		{/if}
	</div>
</a>

<style>
	.card {
		position: relative;
		display: flex;
		flex-direction: column;
		background-color: #faf6f0;
		border: none;
		border-radius: 2px;
		overflow: visible;
		text-decoration: none;
		color: inherit;
		padding: 0.6rem 0.6rem 1.6rem;
		transform: rotate(var(--rotation, 0deg));
		box-shadow:
			0 1px 3px rgba(0, 0, 0, 0.12),
			0 4px 8px rgba(0, 0, 0, 0.06);
		transition:
			transform 0.2s ease,
			box-shadow 0.2s ease;
	}

	/* Yellowed paper tint overlay */
	.card::before {
		content: '';
		position: absolute;
		inset: 0;
		background: rgba(180, 150, 80, var(--paper-yellow, 0.05));
		pointer-events: none;
		border-radius: 2px;
		z-index: 2;
	}

	/* Coffee stain — two overlapping radial gradients */
	.card::after {
		content: '';
		position: absolute;
		inset: 0;
		background:
			radial-gradient(
				ellipse var(--stain-size, 5rem) var(--stain-size, 5rem) at var(--stain-x, 70%)
					var(--stain-y, 30%),
				rgba(120, 80, 30, var(--stain-opacity, 0.1)) 0%,
				rgba(120, 80, 30, calc(var(--stain-opacity, 0.1) * 0.4)) 40%,
				transparent 70%
			),
			radial-gradient(
				ellipse var(--stain2-size, 3rem) var(--stain2-size, 3rem) at var(--stain2-x, 30%)
					var(--stain2-y, 70%),
				rgba(100, 70, 25, var(--stain2-opacity, 0.06)) 0%,
				transparent 60%
			);
		pointer-events: none;
		border-radius: 2px;
		z-index: 3;
	}

	.card:hover {
		transform: rotate(0deg) scale(1.03);
		box-shadow:
			0 4px 12px rgba(0, 0, 0, 0.15),
			0 8px 20px rgba(0, 0, 0, 0.08);
		z-index: 1;
	}

	.card-photo {
		position: relative;
		overflow: hidden;
		border-radius: 1px;
	}

	.card-img {
		width: 100%;
		height: 8rem;
		object-fit: cover;
		filter: sepia(var(--sepia, 0.5)) brightness(var(--brightness, 0.95))
			contrast(var(--contrast, 0.9)) saturate(var(--saturate, 0.7));
	}

	.card-img-placeholder {
		width: 100%;
		height: 8rem;
		background-color: #e8e0d4;
	}

	.card-body {
		padding: var(--size-3) 0 0;
	}

	.card-title {
		font-size: var(--font-size-2);
		font-weight: 600;
		color: #3d3529;
		margin-bottom: var(--size-1);
	}

	/* ---- Dark mode: aged polaroid on a dark surface ---- */
	@media (prefers-color-scheme: dark) {
		.card {
			background-color: #2e2a24;
			box-shadow:
				0 1px 3px rgba(0, 0, 0, 0.4),
				0 4px 8px rgba(0, 0, 0, 0.25);
		}

		/* Paper tint: warmer/subtler on dark background */
		.card::before {
			background: rgba(140, 110, 60, var(--paper-yellow, 0.05));
		}

		/* Coffee stains: darker brown tones */
		.card::after {
			background:
				radial-gradient(
					ellipse var(--stain-size, 5rem) var(--stain-size, 5rem) at var(--stain-x, 70%)
						var(--stain-y, 30%),
					rgba(80, 55, 20, var(--stain-opacity, 0.1)) 0%,
					rgba(80, 55, 20, calc(var(--stain-opacity, 0.1) * 0.4)) 40%,
					transparent 70%
				),
				radial-gradient(
					ellipse var(--stain2-size, 3rem) var(--stain2-size, 3rem) at var(--stain2-x, 30%)
						var(--stain2-y, 70%),
					rgba(60, 40, 15, var(--stain2-opacity, 0.06)) 0%,
					transparent 60%
				);
		}

		.card:hover {
			box-shadow:
				0 4px 12px rgba(0, 0, 0, 0.4),
				0 8px 20px rgba(0, 0, 0, 0.3);
		}

		.card-img {
			filter: sepia(var(--sepia, 0.5)) brightness(calc(var(--brightness, 0.95) * 0.85))
				contrast(var(--contrast, 0.9)) saturate(var(--saturate, 0.7));
		}

		.card-img-placeholder {
			background-color: #3a342b;
		}

		.card-title {
			color: #c8bfb0;
		}
	}
</style>
