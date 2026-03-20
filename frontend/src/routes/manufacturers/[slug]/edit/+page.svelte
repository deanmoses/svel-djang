<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import client from '$lib/api/client';

	let { data } = $props();
	let mfr = $derived(data.manufacturer);

	function mfrToFormFields(m: typeof mfr) {
		return {
			name: m.name,
			description: m.description ?? '',
			year_start: m.year_start ?? '',
			year_end: m.year_end ?? '',
			country: m.country ?? '',
			headquarters: m.headquarters ?? '',
			logo_url: m.logo_url ?? '',
			website: m.website ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => mfrToFormFields(data.manufacturer)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = mfrToFormFields(mfr);
		const changed: Record<string, unknown> = {};
		for (const key of Object.keys(editFields) as (keyof typeof editFields)[]) {
			// Number inputs return NaN when cleared; treat as empty
			let val: unknown = editFields[key];
			if (typeof val === 'number' && isNaN(val)) val = '';
			if (String(val) !== String(original[key])) {
				changed[key] = val === '' ? null : val;
			}
		}
		return changed;
	}

	async function saveChanges() {
		const fields = getChangedFields();
		if (Object.keys(fields).length === 0) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/manufacturers/{slug}/claims/', {
			params: { path: { slug: mfr.slug } },
			body: { fields }
		});

		if (updated) {
			editFields = mfrToFormFields(updated);
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
				<textarea id="ef-description" rows="4" bind:value={editFields.description}></textarea>
			</div>

			<fieldset class="date-group">
				<legend>Years active</legend>
				<div class="date-row">
					<div class="field-group">
						<label for="ef-year-start">Founded</label>
						<input
							id="ef-year-start"
							type="number"
							min="1800"
							max="2100"
							step="1"
							bind:value={editFields.year_start}
						/>
					</div>
					<div class="field-group">
						<label for="ef-year-end">Dissolved</label>
						<input
							id="ef-year-end"
							type="number"
							min="1800"
							max="2100"
							step="1"
							bind:value={editFields.year_end}
						/>
					</div>
				</div>
			</fieldset>

			<div class="field-group">
				<label for="ef-country">Country</label>
				<input id="ef-country" type="text" bind:value={editFields.country} />
			</div>

			<div class="field-group">
				<label for="ef-headquarters">Headquarters</label>
				<input id="ef-headquarters" type="text" bind:value={editFields.headquarters} />
			</div>

			<div class="field-group">
				<label for="ef-website">Website</label>
				<input id="ef-website" type="url" bind:value={editFields.website} />
			</div>

			<div class="field-group">
				<label for="ef-logo-url">Logo URL</label>
				<input id="ef-logo-url" type="url" bind:value={editFields.logo_url} />
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

	.date-group {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-3);
		margin: 0;
	}

	.date-group legend {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		padding: 0 var(--size-1);
	}

	.date-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
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
