<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import type { SectionEditorProps } from '$lib/components/editors/editor-contract';
	import { diffScalarFields } from '$lib/edit-helpers';
	import type { ManufacturerEditView } from './manufacturer-edit-types';
	import {
		saveManufacturerClaims,
		type FieldErrors,
		type SaveMeta,
		type SaveResult
	} from './save-manufacturer-claims';

	type NameFields = {
		name: string;
		slug: string;
	};

	let {
		initialData,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: SectionEditorProps<ManufacturerEditView> = $props();

	function extractFields(manufacturer: ManufacturerEditView): NameFields {
		return {
			name: manufacturer.name,
			slug: manufacturer.slug
		};
	}

	const original = untrack(() => extractFields(initialData));
	let fields = $state<NameFields>({ ...original });
	let fieldErrors = $state<FieldErrors>({});
	let changedFields = $derived(diffScalarFields(fields, original));
	let dirty = $derived(Object.keys(changedFields).length > 0);

	$effect(() => {
		ondirtychange(dirty);
	});

	export function isDirty(): boolean {
		return dirty;
	}

	export async function save(meta?: SaveMeta): Promise<void> {
		fieldErrors = {};
		if (!dirty) {
			onsaved();
			return;
		}

		const result: SaveResult & { updatedSlug?: string } = await saveManufacturerClaims(slug, {
			fields: changedFields,
			...meta
		});

		if (result.ok) {
			if (result.updatedSlug && result.updatedSlug !== slug) {
				const nextPathname = page.url.pathname.replace(`/${slug}`, `/${result.updatedSlug}`);
				await goto(`${nextPathname}${page.url.search}`, { replaceState: true });
			}
			onsaved();
		} else {
			fieldErrors = result.fieldErrors;
			onerror(
				Object.keys(result.fieldErrors).length > 0 ? 'Please fix the errors below.' : result.error
			);
		}
	}
</script>

<div class="editor-fields">
	<TextField label="Name" bind:value={fields.name} error={fieldErrors.name ?? ''} />
	<TextField label="Slug" bind:value={fields.slug} error={fieldErrors.slug ?? ''} />
</div>

<style>
	.editor-fields {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}
</style>
