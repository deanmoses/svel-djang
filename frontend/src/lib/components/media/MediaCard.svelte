<script lang="ts">
	import type { components } from '$lib/api/schema';

	type UploadedMedia = components['schemas']['UploadedMediaSchema'];

	let {
		asset,
		canEdit = false,
		ondelete,
		onsetprimary,
		onclick
	}: {
		asset: UploadedMedia;
		canEdit?: boolean;
		ondelete?: (assetUuid: string) => void;
		onsetprimary?: (assetUuid: string) => void;
		onclick?: (assetUuid: string) => void;
	} = $props();

	function handleDelete(e: MouseEvent) {
		e.stopPropagation();
		if (confirm('Remove this image from this machine?')) {
			ondelete?.(asset.asset_uuid);
		}
	}

	function handleSetPrimary(e: MouseEvent) {
		e.stopPropagation();
		onsetprimary?.(asset.asset_uuid);
	}

	function handleClick() {
		onclick?.(asset.asset_uuid);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onclick?.(asset.asset_uuid);
		}
	}
</script>

<div class="media-card" role="button" tabindex="0" onclick={handleClick} onkeydown={handleKeydown}>
	<div class="thumb-wrapper">
		<img src={asset.renditions.thumb} alt="" class="thumb" loading="lazy" />
		{#if asset.category}
			<span class="badge">{asset.category}</span>
		{/if}
		{#if asset.is_primary}
			<span class="primary-badge" title="Primary image">&#9733;</span>
		{/if}
	</div>

	{#if canEdit}
		<div class="actions">
			{#if !asset.is_primary}
				<button class="action-btn" onclick={handleSetPrimary} title="Set as primary">
					&#9734; Make Primary
				</button>
			{/if}
			<button class="action-btn action-btn--danger" onclick={handleDelete} title="Remove">
				&times; Remove
			</button>
		</div>
	{/if}
</div>

<style>
	.media-card {
		background: var(--color-surface);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		overflow: hidden;
		cursor: pointer;
		transition:
			box-shadow 0.15s ease,
			transform 0.15s ease;
	}

	.media-card:hover {
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
		transform: translateY(-1px);
	}

	.media-card:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	.thumb-wrapper {
		position: relative;
	}

	.thumb {
		width: 100%;
		aspect-ratio: 4 / 3;
		object-fit: cover;
		display: block;
	}

	.badge {
		position: absolute;
		bottom: var(--size-1);
		left: var(--size-1);
		background: rgba(0, 0, 0, 0.65);
		color: #fff;
		font-size: var(--font-size-0);
		padding: 0.1em 0.4em;
		border-radius: var(--radius-1);
	}

	.primary-badge {
		position: absolute;
		top: var(--size-1);
		right: var(--size-1);
		color: #f5c518;
		font-size: 1.25rem;
		line-height: 1;
		filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.5));
	}

	.actions {
		display: flex;
		gap: var(--size-1);
		padding: var(--size-1);
	}

	.action-btn {
		flex: 1;
		background: none;
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-1);
		padding: var(--size-1) var(--size-2);
		font-size: var(--font-size-0);
		cursor: pointer;
		color: var(--color-text-muted);
		transition: color 0.15s ease;
	}

	.action-btn:hover {
		color: var(--color-text);
		border-color: var(--color-border);
	}

	.action-btn--danger:hover {
		color: var(--color-error);
		border-color: var(--color-error);
	}
</style>
