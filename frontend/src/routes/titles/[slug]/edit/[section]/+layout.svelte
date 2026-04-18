<script lang="ts">
	import { setContext } from 'svelte';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { auth } from '$lib/auth.svelte';
	import EditSectionMenu from '$lib/components/EditSectionMenu.svelte';
	import type { EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import {
		findTitleSectionBySegment,
		titleSectionsFor
	} from '$lib/components/editors/title-edit-sections';

	let { children, data } = $props();
	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let currentSection = $derived(
		sectionSegment ? findTitleSectionBySegment(sectionSegment) : undefined
	);
	let isSingleModel = $derived(!!data.title.model_detail);
	let availableSections = $derived(titleSectionsFor(isSingleModel));

	$effect(() => {
		auth.load();
	});

	let editorDirty = $state(false);

	setContext('edit-layout', {
		setDirty(dirty: boolean) {
			editorDirty = dirty;
		}
	});

	let switcherItems: EditSectionMenuItem[] = $derived(
		availableSections.map((s) => ({
			key: s.key,
			label: s.label,
			href: resolve(`/titles/${slug}/edit/${s.segment}`)
		}))
	);
</script>

<div class="edit-shell">
	<header class="edit-header">
		<a href={resolve(`/titles/${slug}`)} class="back-link">&larr; Back</a>
		<h1>
			{#if currentSection}
				<EditSectionMenu
					items={switcherItems}
					currentKey={currentSection.key}
					disabled={editorDirty}
					variant="heading"
				/>
			{:else}
				Edit
			{/if}
		</h1>
	</header>

	{@render children()}
</div>

<style>
	.edit-shell {
		max-width: 48rem;
		margin: 0 auto;
		padding: var(--size-4);
	}

	.edit-header {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: var(--size-4);
	}

	.back-link {
		position: absolute;
		left: 0;
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		text-decoration: none;
	}

	.back-link:hover {
		color: var(--color-text-primary);
	}

	.edit-header h1 {
		font-size: var(--font-size-3);
		font-weight: 600;
		margin: 0;
	}
</style>
