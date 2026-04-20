<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import Button from '$lib/components/Button.svelte';
	import NotesAndCitationsDetails from '$lib/components/NotesAndCitationsDetails.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import { buildEditCitationRequest, type EditCitationSelection } from '$lib/edit-citation';
	import { pageTitle } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
	import { classifyCreateResponse, reconcileSlug, slugifyForCatalog } from '$lib/create-form';
	import { toast } from '$lib/toast/toast.svelte';

	let { data } = $props();

	// svelte-ignore state_referenced_locally
	const initialName = data.initialName;
	const initialSlug = slugifyForCatalog(initialName);
	let name = $state(initialName);
	let slug = $state(initialSlug);
	// Tracks the last slug value written by name-sync. If the user hasn't
	// diverged the slug from this, we keep syncing from name; once they
	// edit the slug to something else, sync stops.
	let syncedSlug = $state(initialSlug);
	let note = $state('');
	let citation = $state<EditCitationSelection | null>(null);

	let formError = $state('');
	let nameError = $state('');
	let slugError = $state('');
	let submitting = $state(false);

	$effect(() => {
		const next = reconcileSlug({ name, slug, syncedSlug });
		if (next.slug !== slug) {
			slug = next.slug;
			syncedSlug = next.syncedSlug;
		}
	});

	async function handleSave() {
		formError = '';
		nameError = '';
		slugError = '';

		if (!name.trim()) {
			nameError = 'Name cannot be blank.';
			return;
		}
		if (!slug.trim()) {
			slugError = 'Slug cannot be blank.';
			return;
		}

		submitting = true;
		try {
			const {
				data: created,
				error,
				response
			} = await client.POST('/api/titles/', {
				body: {
					name: name.trim(),
					slug: slug.trim(),
					note: note || '',
					citation: buildEditCitationRequest(citation)
				}
			});

			const outcome = classifyCreateResponse({ data: created, error, response });
			switch (outcome.kind) {
				case 'ok':
					toast.success(`Created “${outcome.data.name}”.`, { persistUntilNav: true });
					await goto(resolveHref(`/titles/${outcome.slug}`));
					return;
				case 'rate_limited':
					formError = outcome.message;
					return;
				case 'field_errors':
					nameError = outcome.fieldErrors.name ?? '';
					slugError = outcome.fieldErrors.slug ?? '';
					if (!nameError && !slugError) {
						formError = outcome.message;
					}
					return;
				case 'form_error':
					formError = outcome.message;
					return;
			}
		} finally {
			submitting = false;
		}
	}

	function handleCancel() {
		goto(resolve('/titles'));
	}
</script>

<svelte:head>
	<title>{pageTitle('New Title')}</title>
</svelte:head>

<div class="create-page">
	<header class="hdr">
		<h1>New Title</h1>
	</header>

	{#if formError}
		<p class="save-error">{formError}</p>
	{/if}

	<div class="fields">
		<TextField label="Name" bind:value={name} error={nameError} />
		<TextField
			label="Slug"
			bind:value={slug}
			error={slugError}
			placeholder="lowercase-hyphenated"
		/>
	</div>

	<NotesAndCitationsDetails
		bind:note
		bind:citation
		noteLabel="Creation note"
		notePlaceholder="Why are you adding this title?"
	/>

	<div class="form-footer">
		<Button variant="secondary" onclick={handleCancel}>Cancel</Button>
		<Button onclick={handleSave} disabled={submitting}>
			{submitting ? 'Creating…' : 'Create Title'}
		</Button>
	</div>
</div>

<style>
	.create-page {
		max-width: 36rem;
		margin: 0 auto;
		padding: var(--size-6) var(--size-5);
		display: flex;
		flex-direction: column;
		gap: var(--size-4);
	}

	.hdr h1 {
		margin: 0 0 var(--size-2);
	}

	.save-error {
		color: var(--color-error, #d32f2f);
		font-size: var(--font-size-1);
		margin: 0;
	}

	.fields {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}

	.form-footer {
		display: flex;
		justify-content: flex-end;
		gap: var(--size-3);
		margin-top: var(--size-4);
		padding-top: var(--size-3);
		border-top: 1px solid var(--color-border-soft);
	}
</style>
