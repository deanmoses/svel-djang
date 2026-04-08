<script lang="ts">
	import type { Snippet } from 'svelte';
	import { auth } from '$lib/auth.svelte';
	import type { EditCitationSelection } from '$lib/edit-citation';
	import EditCitationField from './EditCitationField.svelte';
	import TextField from './TextField.svelte';

	let {
		saveStatus,
		saveError = '',
		onsave,
		note = $bindable(''),
		citation = $bindable<EditCitationSelection | null>(null),
		showMixedEditWarning = false,
		children
	}: {
		saveStatus: 'idle' | 'saving' | 'saved' | 'error';
		saveError?: string;
		onsave: () => void;
		note?: string;
		citation?: EditCitationSelection | null;
		showMixedEditWarning?: boolean;
		children: Snippet;
	} = $props();
</script>

{#if auth.isAuthenticated}
	<section class="edit-form">
		<h2>Edit</h2>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				onsave();
			}}
		>
			{@render children()}

			<TextField
				label="Edit note"
				bind:value={note}
				placeholder="Why are you making this change?"
				optional
			/>
			<EditCitationField bind:citation {showMixedEditWarning} />

			<div class="form-actions">
				<button type="submit" class="btn-save" disabled={saveStatus === 'saving'}>
					{saveStatus === 'saving' ? 'Saving\u2026' : 'Save changes'}
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
		color: var(--color-error);
	}
</style>
