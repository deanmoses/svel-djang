<script lang="ts">
	import { untrack } from 'svelte';
	import { goto, invalidateAll } from '$app/navigation';
	import { resolveHref } from '$lib/utils';
	import client from '$lib/api/client';
	import {
		shouldShowMixedEditCitationWarning,
		type EditCitationSelection,
		withEditMetadata
	} from '$lib/edit-citation';
	import { getEditRedirectHref } from '$lib/edit-routes';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
	import TextAreaField from '$lib/components/form/TextAreaField.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import { buildModelBoundary, buildTitlePatchBody, titleToFormState } from '../title-edit';

	let { data } = $props();
	let title = $derived(data.title);
	let boundary = $derived(buildModelBoundary(title));

	let editFields = $state(untrack(() => titleToFormState(data.title)));
	let selectedFranchise = $state<string | null>(untrack(() => data.title.franchise?.slug ?? null));
	let editNote = $state('');
	let editCitation = $state<EditCitationSelection | null>(null);
	let pendingBody = $derived(
		buildTitlePatchBody({ ...editFields, franchiseSlug: selectedFranchise ?? '' }, title)
	);
	let showMixedEditWarning = $derived(
		shouldShowMixedEditCitationWarning(pendingBody, editCitation)
	);

	let franchiseOptions = $state<{ slug: string; label: string; count: number }[]>([]);

	$effect(() => {
		client.GET('/api/franchises/all/').then(({ data: franchises }) => {
			if (franchises) {
				franchiseOptions = franchises.map((franchise) => ({
					slug: franchise.slug,
					label: franchise.name,
					count: franchise.title_count
				}));
			}
		});
	});

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	async function saveChanges() {
		const rawBody = pendingBody;
		if (!rawBody) return;
		const body = withEditMetadata(rawBody, editNote, editCitation);

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/titles/{slug}/claims/', {
			params: { path: { slug: title.slug } },
			body
		});

		if (updated) {
			const redirectHref = getEditRedirectHref('titles', title.slug, updated.slug);
			editFields = titleToFormState(updated);
			selectedFranchise = updated.franchise?.slug ?? null;
			editNote = '';
			editCitation = null;
			if (redirectHref) {
				await goto(redirectHref, { replaceState: true });
				return;
			}
			await invalidateAll();
			saveStatus = 'saved';
			setTimeout(() => (saveStatus = 'idle'), 3000);
		} else {
			saveStatus = 'error';
			saveError = error ? JSON.stringify(error) : 'Save failed.';
		}
	}
</script>

<EditFormShell
	{saveStatus}
	{saveError}
	onsave={saveChanges}
	bind:note={editNote}
	bind:citation={editCitation}
	{showMixedEditWarning}
>
	{#if boundary.singleModelActions}
		<section class="merged-note">
			<h3>Merged Single-Model View</h3>
			<p>
				This title has one model, and the public detail page merges title and model information. You
				are editing title-owned facts here.
			</p>
			<div class="merged-actions">
				<a href={resolveHref(boundary.singleModelActions.editHref)}>Edit model facts</a>
				<a href={resolveHref(boundary.singleModelActions.sourcesHref)}>Model sources</a>
			</div>
		</section>
	{/if}

	<section class="boundary">
		<h3>Model-Owned Facts</h3>
		<p>
			Credits, machine roster, variants, specifications, ratings, external IDs, and other
			model-specific metadata stay read-only here.
		</p>

		<ul class="boundary-list">
			<li>People and credits</li>
			<li>Machine roster and variants</li>
			<li>Specifications, ratings, and production data</li>
			<li>External IDs and model-specific metadata</li>
		</ul>

		{#if boundary.modelLinks.length > 0}
			<div class="boundary-links">
				<span class="boundary-label">Models in this title</span>
				<ul>
					{#each boundary.modelLinks as model (model.slug)}
						<li><a href={resolveHref(`/models/${model.slug}`)}>{model.name}</a></li>
					{/each}
				</ul>
			</div>
		{/if}
	</section>

	<TextField label="Name" bind:value={editFields.name} />
	<TextField label="Slug" bind:value={editFields.slug} />
	<MarkdownTextArea label="Description" bind:value={editFields.description} rows={6} />

	<div class="field-group">
		<SearchableSelect
			label="Franchise"
			options={franchiseOptions}
			bind:selected={selectedFranchise}
			allowZeroCount
			placeholder="Search franchises..."
		/>
	</div>

	<TextAreaField label="Abbreviations" bind:value={editFields.abbreviationsText} rows={3} />
	<p class="field-help">Separate abbreviations with commas or new lines.</p>
</EditFormShell>

<style>
	.merged-note,
	.boundary {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-4);
		background: var(--color-surface-2, rgba(0, 0, 0, 0.02));
	}

	.merged-note {
		margin-bottom: var(--size-4);
	}

	.merged-note h3,
	.boundary h3 {
		margin: 0 0 var(--size-2);
		font-size: var(--font-size-2);
	}

	.merged-note p,
	.boundary p {
		margin: 0 0 var(--size-3);
		color: var(--color-text-muted);
	}

	.boundary-list,
	.boundary-links ul {
		margin: 0;
		padding-left: var(--size-4);
	}

	.boundary-links {
		margin-top: var(--size-3);
	}

	.boundary-label {
		display: block;
		margin-bottom: var(--size-1);
		font-weight: 600;
	}

	.merged-actions {
		display: flex;
		gap: var(--size-4);
	}

	.field-help {
		margin: calc(var(--size-3) * -1) 0 0;
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}
</style>
