<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import client from '$lib/api/client';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';

	let { data } = $props();
	let theme = $derived(data.theme);

	// --- Form state ---

	function toFormFields(t: typeof theme) {
		return {
			name: t.name,
			description: t.description?.text ?? ''
		};
	}

	let editFields = $state(untrack(() => toFormFields(data.theme)));
	let selectedParents = $state<string[]>(
		untrack(() => (data.theme.parents ?? []).map((p: { slug: string }) => p.slug))
	);
	let editNote = $state('');

	// --- Parent options (loaded async) ---

	let parentOptions = $state<{ slug: string; label: string; count: number }[]>([]);

	$effect(() => {
		const slug = untrack(() => theme.slug);
		client.GET('/api/themes/').then(({ data: themes }) => {
			if (themes) {
				parentOptions = themes
					.filter((t) => t.slug !== slug)
					.map((t) => ({ slug: t.slug, label: t.name, count: 0 }));
			}
		});
	});

	// --- Change detection ---

	function getChangedScalarFields(): Record<string, unknown> {
		const original = toFormFields(theme);
		const changed: Record<string, unknown> = {};
		for (const key of Object.keys(editFields) as (keyof typeof editFields)[]) {
			if (String(editFields[key]) !== String(original[key])) {
				changed[key] = editFields[key] === '' ? null : editFields[key];
			}
		}
		return changed;
	}

	function parentsChanged(): boolean {
		const original = (theme.parents ?? []).map((p: { slug: string }) => p.slug).sort();
		const current = [...selectedParents].sort();
		return JSON.stringify(original) !== JSON.stringify(current);
	}

	// --- Save ---

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	async function saveChanges() {
		const fields = getChangedScalarFields();
		const hasFields = Object.keys(fields).length > 0;
		const hasParents = parentsChanged();

		if (!hasFields && !hasParents) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/themes/{slug}/claims/', {
			params: { path: { slug: theme.slug } },
			body: {
				fields: hasFields ? fields : {},
				parents: hasParents ? selectedParents : null,
				note: editNote.trim()
			}
		});

		if (updated) {
			editFields = toFormFields(updated);
			selectedParents = (updated.parents ?? []).map((p) => p.slug);
			editNote = '';
			await invalidateAll();
			saveStatus = 'saved';
			setTimeout(() => (saveStatus = 'idle'), 3000);
		} else {
			saveStatus = 'error';
			saveError = error ? JSON.stringify(error) : 'Save failed.';
		}
	}
</script>

{#if auth.isAuthenticated}
	<section class="edit-form">
		<h2>Edit</h2>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				saveChanges();
			}}
		>
			<div class="field-group">
				<label for="ef-name">Name</label>
				<input id="ef-name" type="text" bind:value={editFields.name} />
			</div>

			<div class="field-group">
				<label for="ef-description">Description</label>
				<textarea id="ef-description" rows="6" bind:value={editFields.description}></textarea>
			</div>

			<div class="field-group">
				<SearchableSelect
					label="Parents"
					options={parentOptions}
					bind:selected={selectedParents}
					multi
					allowZeroCount
					placeholder="Search themes..."
				/>
			</div>

			<div class="field-group">
				<label for="ef-note">Edit note <span class="optional">(optional)</span></label>
				<input
					id="ef-note"
					type="text"
					placeholder="Why are you making this change?"
					bind:value={editNote}
				/>
			</div>

			<div class="form-actions">
				<button type="submit" class="btn-save" disabled={saveStatus === 'saving'}>
					{saveStatus === 'saving' ? 'Saving…' : 'Save changes'}
				</button>
				{#if saveStatus === 'saved'}
					<span class="save-feedback saved">Saved</span>
				{/if}
				{#if saveStatus === 'error'}
					<span class="save-feedback error">{saveError}</span>
				{/if}
			</div>
		</form>
	</section>
{:else}
	<p class="not-authenticated">Sign in to edit this record.</p>
{/if}

<style>
	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.edit-form {
		margin-bottom: var(--size-6);
	}

	form {
		display: flex;
		flex-direction: column;
		gap: var(--size-4);
	}

	.field-group {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
	}

	.field-group label {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
	}

	.field-group input,
	.field-group textarea {
		font-size: var(--font-size-1);
		color: var(--color-text-primary);
		background-color: var(--color-surface);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-2) var(--size-3);
		width: 100%;
		font-family: inherit;
	}

	.field-group input:focus,
	.field-group textarea:focus {
		outline: 2px solid var(--color-accent);
		outline-offset: -1px;
		border-color: var(--color-accent);
	}

	textarea {
		resize: vertical;
	}

	.optional {
		font-weight: 400;
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.form-actions {
		display: flex;
		align-items: center;
		gap: var(--size-4);
	}

	.btn-save {
		padding: var(--size-2) var(--size-5);
		font-size: var(--font-size-1);
		font-weight: 600;
		color: #fff;
		background-color: var(--color-accent);
		border: none;
		border-radius: var(--radius-2);
		cursor: pointer;
	}

	.btn-save:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.save-feedback {
		font-size: var(--font-size-1);
	}

	.save-feedback.saved {
		color: var(--color-accent);
	}

	.save-feedback.error {
		color: var(--color-error, #c0392b);
	}

	.not-authenticated {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}
</style>
