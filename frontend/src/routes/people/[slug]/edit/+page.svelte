<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import client from '$lib/api/client';

	let { data } = $props();
	let person = $derived(data.person);

	function personToFormFields(p: typeof person) {
		return {
			name: p.name,
			description: p.description?.text ?? '',
			nationality: p.nationality ?? '',
			birth_year: p.birth_year ?? '',
			birth_month: p.birth_month ?? '',
			birth_day: p.birth_day ?? '',
			death_year: p.death_year ?? '',
			death_month: p.death_month ?? '',
			death_day: p.death_day ?? '',
			birth_place: p.birth_place ?? '',
			photo_url: p.photo_url ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => personToFormFields(data.person)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = personToFormFields(person);
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

		const { data: updated, error } = await client.PATCH('/api/people/{slug}/claims/', {
			params: { path: { slug: person.slug } },
			body: { fields }
		});

		if (updated) {
			editFields = personToFormFields(updated);
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
				<label for="ef-nationality">Nationality</label>
				<input id="ef-nationality" type="text" bind:value={editFields.nationality} />
			</div>

			<fieldset class="date-group">
				<legend>Born</legend>
				<div class="date-row">
					<div class="field-group">
						<label for="ef-birth-year">Year</label>
						<input
							id="ef-birth-year"
							type="number"
							min="1800"
							max="2100"
							step="1"
							bind:value={editFields.birth_year}
						/>
					</div>
					<div class="field-group">
						<label for="ef-birth-month">Month</label>
						<input
							id="ef-birth-month"
							type="number"
							min="1"
							max="12"
							step="1"
							bind:value={editFields.birth_month}
						/>
					</div>
					<div class="field-group">
						<label for="ef-birth-day">Day</label>
						<input
							id="ef-birth-day"
							type="number"
							min="1"
							max="31"
							step="1"
							bind:value={editFields.birth_day}
						/>
					</div>
				</div>
			</fieldset>

			<div class="field-group">
				<label for="ef-birth-place">Birth place</label>
				<input id="ef-birth-place" type="text" bind:value={editFields.birth_place} />
			</div>

			<fieldset class="date-group">
				<legend>Died</legend>
				<div class="date-row">
					<div class="field-group">
						<label for="ef-death-year">Year</label>
						<input
							id="ef-death-year"
							type="number"
							min="1800"
							max="2100"
							step="1"
							bind:value={editFields.death_year}
						/>
					</div>
					<div class="field-group">
						<label for="ef-death-month">Month</label>
						<input
							id="ef-death-month"
							type="number"
							min="1"
							max="12"
							step="1"
							bind:value={editFields.death_month}
						/>
					</div>
					<div class="field-group">
						<label for="ef-death-day">Day</label>
						<input
							id="ef-death-day"
							type="number"
							min="1"
							max="31"
							step="1"
							bind:value={editFields.death_day}
						/>
					</div>
				</div>
			</fieldset>

			<div class="field-group">
				<label for="ef-photo-url">Photo URL</label>
				<input id="ef-photo-url" type="url" bind:value={editFields.photo_url} />
			</div>

			<div class="field-group">
				<label for="ef-description">Bio</label>
				<textarea id="ef-description" rows="8" bind:value={editFields.description}></textarea>
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
		grid-template-columns: 1fr 1fr 1fr;
		gap: var(--size-3);
	}

	.date-row .field-group input {
		width: 100%;
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
