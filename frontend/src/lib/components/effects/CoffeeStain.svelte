<script lang="ts">
	/**
	 * Self-contained coffee stain overlay.
	 *
	 * Renders an absolutely-positioned SVG that covers its nearest positioned
	 * parent. Uses SVG turbulence to generate organic blob shapes — each
	 * instance gets a unique noise pattern via the `seed` prop.
	 *
	 * The parent element must have `position: relative` (or similar).
	 */
	let {
		seed,
		frequency = 0.035,
		octaves = 5,
		opacity = 0.12,
		blur = 4,
		threshold = '0 0 0 0 0 0 0.5 0.7',
		color = 'rgb(120, 80, 30)',
		x = '0%',
		y = '0%',
		width = '100%',
		height = '100%'
	}: {
		seed: number;
		frequency?: number;
		octaves?: number;
		opacity?: number;
		blur?: number;
		threshold?: string;
		color?: string;
		x?: string;
		y?: string;
		width?: string;
		height?: string;
	} = $props();

	const filterId = `stain-${crypto.randomUUID()}`;
</script>

<svg class="coffee-stain" aria-hidden="true">
	<defs>
		<filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
			<feTurbulence
				type="fractalNoise"
				baseFrequency={frequency}
				numOctaves={octaves}
				{seed}
				result="noise"
			/>
			<feComponentTransfer in="noise" result="blobs">
				<feFuncA type="discrete" tableValues={threshold} />
			</feComponentTransfer>
			<feFlood flood-color={color} flood-opacity={opacity} result="color" />
			<feComposite in="color" in2="blobs" operator="in" result="stain" />
			<feGaussianBlur in="stain" stdDeviation={blur} />
		</filter>
	</defs>
	<rect {x} {y} {width} {height} filter="url(#{filterId})" />
</svg>

<style>
	.coffee-stain {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		z-index: 3;
		overflow: hidden;
	}
</style>
