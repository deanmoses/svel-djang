<script lang="ts">
	import type { Snippet } from 'svelte';
	import CoffeeStain from '../effects/CoffeeStain.svelte';
	import WearEffect from './WearEffect.svelte';

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

	const rand = (min: number, max: number) => Math.random() * (max - min) + min;
	const randInt = (max: number) => Math.floor(Math.random() * max);

	// Film grain filter (unique per card)
	const grainId = `grain-${crypto.randomUUID()}`;
	const grainSeed = randInt(1000);

	// Stain seeds and positions
	const stain1 = { seed: randInt(1000), x: `${rand(-5, 55)}%`, y: `${rand(-5, 55)}%` };
	const stain2 = { seed: randInt(1000), x: `${rand(-5, 65)}%`, y: `${rand(-5, 65)}%` };

	// Photo aging — all declarative, no action needed
	const rotation = `${rand(-3, 3)}deg`;
	const sepia = `${rand(0.3, 0.7)}`;
	const brightness = `${rand(0.9, 1.05)}`;
	const contrast = `${rand(0.85, 0.95)}`;
	const saturate = `${rand(0.6, 0.85)}`;
	const paperYellow = `${rand(0.03, 0.08)}`;

	// Wear effect: ~40% of cards get one
	type WearType = 'none' | 'dog-ear' | 'crease' | 'torn-corner';
	const wearRoll = Math.random();
	const wearType: WearType =
		wearRoll < 0.6
			? 'none'
			: wearRoll < 0.73
				? 'dog-ear'
				: wearRoll < 0.87
					? 'crease'
					: 'torn-corner';

	const corners = ['tr', 'tl', 'br', 'bl'] as const;
	const wearCorner = corners[randInt(corners.length)];
	const creaseAngle = -25 + Math.random() * 50;
	const creasePos = 30 + Math.random() * 40;
	const earSize = 1 + Math.random() * 0.8;
</script>

<!-- Film grain filter definition -->
<svg class="svg-filters" aria-hidden="true">
	<defs>
		<filter id={grainId} x="0%" y="0%" width="100%" height="100%">
			<feTurbulence
				type="fractalNoise"
				baseFrequency="0.7"
				numOctaves="3"
				seed={grainSeed}
				result="grain"
			/>
			<feColorMatrix type="saturate" values="0" in="grain" result="grainMono" />
			<feBlend in="SourceGraphic" in2="grainMono" mode="multiply" />
		</filter>
	</defs>
</svg>

<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- href is pre-resolved by caller -->
<a
	{href}
	class="card"
	style:--rotation={rotation}
	style:--sepia={sepia}
	style:--brightness={brightness}
	style:--contrast={contrast}
	style:--saturate={saturate}
	style:--paper-yellow={paperYellow}
	style:--grain-url="url(#{grainId})"
>
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

	<CoffeeStain
		seed={stain1.seed}
		x={stain1.x}
		y={stain1.y}
		width="40%"
		height="40%"
		opacity={0.15}
		blur={3}
		threshold="0 0 0 0 0 0 0.6 0.8"
	/>
	<CoffeeStain
		seed={stain2.seed}
		frequency={0.045}
		octaves={4}
		x={stain2.x}
		y={stain2.y}
		width="30%"
		height="30%"
		opacity={0.1}
		blur={4}
		threshold="0 0 0 0 0 0 0 0.5"
		color="rgb(100, 65, 20)"
	/>

	{#if wearType !== 'none'}
		<WearEffect type={wearType} corner={wearCorner} {earSize} {creaseAngle} {creasePos} />
	{/if}
</a>

<style>
	.svg-filters {
		position: absolute;
		width: 0;
		height: 0;
		overflow: hidden;
		pointer-events: none;
	}

	.card {
		/* Color tokens — overridden in dark mode */
		--polaroid-paper: #faf6f0;
		--polaroid-paper-dim: #e8e0d4;
		--polaroid-ink: #3d3529;

		position: relative;
		display: flex;
		flex-direction: column;
		background-color: var(--polaroid-paper);
		border: none;
		border-radius: 2px;
		overflow: hidden;
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
		filter: var(--grain-url) sepia(var(--sepia, 0.5)) brightness(var(--brightness, 0.95))
			contrast(var(--contrast, 0.9)) saturate(var(--saturate, 0.7));
	}

	.card-img-placeholder {
		width: 100%;
		height: 8rem;
		background-color: var(--polaroid-paper-dim);
	}

	.card-body {
		padding: var(--size-3) 0 0;
	}

	.card-title {
		font-size: var(--font-size-2);
		font-weight: 600;
		color: var(--polaroid-ink);
		margin-bottom: var(--size-1);
	}

	/* ---- Dark mode ---- */
	@media (prefers-color-scheme: dark) {
		.card {
			--polaroid-paper: #2e2a24;
			--polaroid-paper-dim: #3a342b;
			--polaroid-ink: #c8bfb0;

			box-shadow:
				0 1px 3px rgba(0, 0, 0, 0.4),
				0 4px 8px rgba(0, 0, 0, 0.25);
		}

		.card::before {
			background: rgba(140, 110, 60, var(--paper-yellow, 0.05));
		}

		.card:hover {
			box-shadow:
				0 4px 12px rgba(0, 0, 0, 0.4),
				0 8px 20px rgba(0, 0, 0, 0.3);
		}

		.card-img {
			filter: var(--grain-url) sepia(var(--sepia, 0.5))
				brightness(calc(var(--brightness, 0.95) * 0.85)) contrast(var(--contrast, 0.9))
				saturate(var(--saturate, 0.7));
		}
	}
</style>
