<script lang="ts">
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import { IMAGE_ACCEPT } from '$lib/api/media-api';
	import { createUploadManager } from '$lib/media-upload.svelte';
	import Button from '$lib/components/Button.svelte';

	let {
		entityType,
		slug,
		categories = [...MEDIA_CATEGORIES.model] as string[],
		onuploaded
	}: {
		entityType: string;
		slug: string;
		categories?: readonly string[];
		onuploaded: () => void;
	} = $props();

	let fileInput: HTMLInputElement | undefined = $state();
	// svelte-ignore state_referenced_locally
	let category = $state(categories[0] ?? '');
	let isPrimary = $state(false);
	let isDragging = $state(false);

	const manager = createUploadManager();

	function openPicker() {
		fileInput?.click();
	}

	async function handleFiles() {
		const files = fileInput?.files;
		if (!files || files.length === 0) return;
		await processFiles(files);
		if (fileInput) fileInput.value = '';
	}

	async function processFiles(files: FileList) {
		await manager.upload(files, entityType, slug, { category, isPrimary });

		const hadError = manager.files.some((f) => f.status === 'error');

		if (!hadError) {
			manager.reset();
			onuploaded();
		}
	}

	function handleDragEnter(e: DragEvent) {
		e.preventDefault();
		isDragging = true;
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
	}

	function handleDragLeave(e: DragEvent) {
		if (e.currentTarget === e.target || !e.relatedTarget) {
			isDragging = false;
		}
	}

	async function handleDrop(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
		const files = e.dataTransfer?.files;
		if (!files || files.length === 0) return;
		await processFiles(files);
	}
</script>

<div class="upload-page">
	<div class="options">
		<label class="option-label">
			Category
			<select bind:value={category} class="category-select">
				{#each categories as cat (cat)}
					<option value={cat}>{cat}</option>
				{/each}
			</select>
		</label>

		<label class="option-label">
			<input type="checkbox" bind:checked={isPrimary} />
			Set as primary
		</label>
	</div>

	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="drop-zone"
		class:dragging={isDragging}
		ondragenter={handleDragEnter}
		ondragover={handleDragOver}
		ondragleave={handleDragLeave}
		ondrop={handleDrop}
	>
		<div class="drop-zone-content">
			<span class="drop-icon">&#8683;</span>
			<p class="drop-text">Drag and drop images here</p>
			<p class="drop-or">or</p>
			<Button onclick={openPicker} disabled={manager.isUploading}>Choose Files</Button>
		</div>
	</div>

	<input
		bind:this={fileInput}
		type="file"
		accept={IMAGE_ACCEPT}
		multiple
		class="hidden-input"
		onchange={handleFiles}
	/>

	{#if manager.files.length > 0}
		<div class="file-list-header">
			<span class="file-list-title">
				{#if manager.isUploading}
					Uploading...
				{:else}
					Upload results
				{/if}
			</span>
		</div>
		<ul class="file-list">
			{#each manager.files as entry, i (entry.file.name + entry.file.lastModified + i)}
				<li class="file-entry" class:error={entry.status === 'error'}>
					<span class="file-name">{entry.file.name}</span>
					<span class="file-status">
						{#if entry.status === 'uploading' && entry.progress >= 100}
							Processing...
						{:else if entry.status === 'uploading'}
							<span class="progress-bar">
								<span class="progress-fill" style:width="{entry.progress}%"></span>
							</span>
							{entry.progress}%
						{:else if entry.status === 'success'}
							Done
						{:else if entry.status === 'error'}
							{entry.error}
						{:else}
							Pending
						{/if}
					</span>
				</li>
			{/each}
		</ul>
		{#if !manager.isUploading}
			<div class="view-uploads">
				<Button onclick={onuploaded}>View Uploads</Button>
			</div>
		{/if}
	{/if}
</div>

<style>
	.upload-page {
		max-width: 36rem;
	}

	.options {
		display: flex;
		align-items: center;
		gap: var(--size-4);
		flex-wrap: wrap;
		margin-bottom: var(--size-4);
	}

	.option-label {
		display: flex;
		align-items: center;
		gap: var(--size-2);
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	.category-select {
		padding: var(--size-1) var(--size-2);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		background: var(--color-surface);
		color: var(--color-text);
		font-size: var(--font-size-1);
	}

	.drop-zone {
		border: 2px dashed var(--color-border-soft);
		border-radius: var(--radius-3, 0.5rem);
		padding: var(--size-8, 3rem) var(--size-4);
		text-align: center;
		transition:
			border-color 0.15s ease,
			background-color 0.15s ease;
	}

	.drop-zone.dragging {
		border-color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 5%, transparent);
	}

	.drop-zone-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--size-1);
	}

	.drop-icon {
		font-size: 2.5rem;
		line-height: 1;
		color: var(--color-text-muted);
		opacity: 0.5;
	}

	.drop-text {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		margin: 0;
	}

	.drop-or {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		margin: 0;
	}

	.hidden-input {
		display: none;
	}

	.file-list-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: var(--size-4);
	}

	.file-list-title {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	.file-list {
		list-style: none;
		padding: 0;
		margin: var(--size-2) 0 0;
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
	}

	.file-entry {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--size-3);
		font-size: var(--font-size-0);
		padding: var(--size-1) var(--size-2);
		border-radius: var(--radius-1);
		background: var(--color-surface);
	}

	.file-entry.error {
		color: var(--color-error);
	}

	.file-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.file-status {
		display: flex;
		align-items: center;
		gap: var(--size-2);
		white-space: nowrap;
		flex-shrink: 0;
	}

	.progress-bar {
		width: 6rem;
		height: 0.4rem;
		background: var(--color-border-soft);
		border-radius: 999px;
		overflow: hidden;
	}

	.progress-fill {
		display: block;
		height: 100%;
		background: var(--color-accent);
		transition: width 0.15s ease;
	}

	.view-uploads {
		margin-top: var(--size-4);
	}
</style>
