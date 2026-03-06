<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import client from '$lib/api/client';

	let { data } = $props();
	let model = $derived(data.model);

	function modelToFormFields(m: typeof model) {
		return {
			name: m.name,
			year: m.year ?? '',
			month: m.month ?? '',
			player_count: m.player_count ?? '',
			flipper_count: m.flipper_count ?? '',
			production_quantity: m.production_quantity,
			ipdb_id: m.ipdb_id ?? '',
			opdb_id: m.opdb_id ?? '',
			pinside_id: m.pinside_id ?? '',
			ipdb_rating: m.ipdb_rating ?? '',
			pinside_rating: m.pinside_rating ?? '',
			educational_text: m.educational_text,
			sources_notes: m.sources_notes
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => modelToFormFields(data.model)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = modelToFormFields(model);
		const changed: Record<string, unknown> = {};
		for (const key of Object.keys(editFields) as (keyof typeof editFields)[]) {
			const val = editFields[key];
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

		const { data: updated, error } = await client.PATCH('/api/models/{slug}/claims/', {
			params: { path: { slug: model.slug } },
			body: { fields }
		});

		if (updated) {
			editFields = modelToFormFields(updated);
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

			<div class="form-row">
				<div class="field-group">
					<label for="ef-year">Year</label>
					<input id="ef-year" type="number" min="1940" max="2100" bind:value={editFields.year} />
				</div>
				<div class="field-group">
					<label for="ef-month">Month</label>
					<input id="ef-month" type="number" min="1" max="12" bind:value={editFields.month} />
				</div>
			</div>

			<div class="form-row">
				<div class="field-group">
					<label for="ef-players">Players</label>
					<input
						id="ef-players"
						type="number"
						min="1"
						max="8"
						bind:value={editFields.player_count}
					/>
				</div>
				<div class="field-group">
					<label for="ef-flippers">Flippers</label>
					<input
						id="ef-flippers"
						type="number"
						min="0"
						max="10"
						bind:value={editFields.flipper_count}
					/>
				</div>
			</div>

			<div class="field-group">
				<label for="ef-production">Production quantity</label>
				<input
					id="ef-production"
					type="number"
					min="0"
					bind:value={editFields.production_quantity}
				/>
			</div>

			<fieldset>
				<legend>Cross-reference IDs</legend>
				<div class="form-row">
					<div class="field-group">
						<label for="ef-ipdb">IPDB ID</label>
						<input id="ef-ipdb" type="number" min="1" bind:value={editFields.ipdb_id} />
					</div>
					<div class="field-group">
						<label for="ef-opdb">OPDB ID</label>
						<input id="ef-opdb" type="text" bind:value={editFields.opdb_id} />
					</div>
					<div class="field-group">
						<label for="ef-pinside">Pinside ID</label>
						<input id="ef-pinside" type="number" min="1" bind:value={editFields.pinside_id} />
					</div>
				</div>
			</fieldset>

			<fieldset>
				<legend>Ratings</legend>
				<div class="form-row">
					<div class="field-group">
						<label for="ef-ipdb-rating">IPDB rating</label>
						<input
							id="ef-ipdb-rating"
							type="number"
							min="0"
							max="10"
							step="0.01"
							bind:value={editFields.ipdb_rating}
						/>
					</div>
					<div class="field-group">
						<label for="ef-pinside-rating">Pinside rating</label>
						<input
							id="ef-pinside-rating"
							type="number"
							min="0"
							max="10"
							step="0.01"
							bind:value={editFields.pinside_rating}
						/>
					</div>
				</div>
			</fieldset>

			<div class="field-group">
				<label for="ef-educational">About / educational text</label>
				<textarea id="ef-educational" rows="6" bind:value={editFields.educational_text}></textarea>
			</div>

			<div class="field-group">
				<label for="ef-sources-notes">Sources notes</label>
				<textarea id="ef-sources-notes" rows="4" bind:value={editFields.sources_notes}></textarea>
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

	fieldset {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-4);
		display: flex;
		flex-direction: column;
		gap: var(--size-4);
	}

	legend {
		font-size: var(--font-size-1);
		font-weight: 600;
		color: var(--color-text-muted);
		padding: 0 var(--size-2);
	}

	.form-row {
		display: flex;
		gap: var(--size-4);
	}

	.form-row .field-group {
		flex: 1;
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
	.field-group select,
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
	.field-group select:focus,
	.field-group textarea:focus {
		outline: 2px solid var(--color-accent);
		outline-offset: -1px;
		border-color: var(--color-accent);
	}

	textarea {
		resize: vertical;
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
