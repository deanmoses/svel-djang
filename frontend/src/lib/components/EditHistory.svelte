<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import type { components } from '$lib/api/schema';
	import { auth } from '$lib/auth.svelte';
	import FocusContentShell from './FocusContentShell.svelte';
	import InlineDiff from './InlineDiff.svelte';
	import UserBadge from './UserBadge.svelte';
	import { SvelteMap, SvelteSet } from 'svelte/reactivity';
	import { getEntityContext } from '$lib/entity-context';
	import { isDiffable, formatValue } from './change-display';
	import SmartDate from './SmartDate.svelte';

	type ChangeSet = components['schemas']['ChangeSetSchema'];
	type FieldChange = components['schemas']['FieldChangeSchema'];

	let { changesets }: { changesets: ChangeSet[] } = $props();
	const entity = getEntityContext();

	let revertingClaimId = $state<number | null>(null);
	let revertNote = $state('');
	let revertError = $state<string | null>(null);
	let revertLoading = $state(false);

	interface RetractionInfo {
		user_display: string | null | undefined;
		created_at: string;
		note: string;
	}

	/**
	 * Build a lookup: claim_id → retraction info from the revert changeset.
	 * Keyed by claim_id (not claim_key) so repeated reverts of the same
	 * field each get their own attribution.
	 */
	let retractionLookup = $derived.by(() => {
		const lookup = new SvelteMap<number, RetractionInfo>();
		for (const cs of changesets) {
			for (const r of cs.retractions ?? []) {
				lookup.set(r.claim_id, {
					user_display: cs.user_display,
					created_at: cs.created_at,
					note: cs.note
				});
			}
		}
		return lookup;
	});

	/** Set of claim_ids that appear in retractions (for suppressing revert cards). */
	let matchedRetractionIds = $derived.by(() => {
		const ids = new SvelteSet<number>();
		for (const cs of changesets) {
			for (const change of cs.changes) {
				if (
					change.is_retracted &&
					change.claim_id != null &&
					retractionLookup.has(change.claim_id)
				) {
					ids.add(change.claim_id);
				}
			}
		}
		return ids;
	});

	/**
	 * A changeset is "empty" when all its visual content has been absorbed
	 * elsewhere (retractions shown inline on original changes). Hide these
	 * to avoid blank cards.
	 */
	function isEmptyChangeset(cs: ChangeSet): boolean {
		const hasChanges = cs.changes.length > 0;
		const hasUnmatchedRetractions = (cs.retractions ?? []).some(
			(r) => !matchedRetractionIds.has(r.claim_id)
		);
		return !hasChanges && !hasUnmatchedRetractions;
	}

	function canRevert(change: FieldChange): boolean {
		return (
			auth.isAuthenticated &&
			change.is_active === true &&
			change.claim_user_id !== null &&
			change.claim_id !== null
		);
	}

	function startRevert(claimId: number) {
		revertingClaimId = claimId;
		revertNote = '';
		revertError = null;
	}

	function cancelRevert() {
		revertingClaimId = null;
		revertNote = '';
		revertError = null;
	}

	async function submitRevert() {
		if (!revertingClaimId || !revertNote.trim()) return;
		revertLoading = true;
		revertError = null;

		const { error } = await client.POST('/api/provenance/claims/{claim_id}/revert/', {
			params: { path: { claim_id: revertingClaimId } },
			body: { note: revertNote }
		});

		revertLoading = false;

		if (error) {
			revertError = (error as { detail?: string }).detail ?? 'Revert failed.';
		} else {
			revertingClaimId = null;
			revertNote = '';
			await invalidateAll();
		}
	}
</script>

{#snippet revertControls(change: FieldChange)}
	{#if canRevert(change)}
		<div class="revert-cell">
			{#if revertingClaimId === change.claim_id}
				<div class="revert-form">
					<input
						type="text"
						bind:value={revertNote}
						placeholder="Reason for reverting…"
						class="revert-input"
						disabled={revertLoading}
					/>
					<div class="revert-actions">
						<button
							class="btn-revert-submit"
							onclick={submitRevert}
							disabled={revertLoading || !revertNote.trim()}
						>
							{revertLoading ? 'Reverting…' : 'Confirm'}
						</button>
						<button class="btn-revert-cancel" onclick={cancelRevert} disabled={revertLoading}>
							Cancel
						</button>
					</div>
					{#if revertError}
						<p class="revert-error">{revertError}</p>
					{/if}
				</div>
			{:else}
				<button
					class="btn-revert"
					class:btn-revert-dim={change.is_winning === false}
					title={change.is_winning === false
						? "This change doesn't affect the current page"
						: 'Revert this change'}
					onclick={() => startRevert(change.claim_id!)}
				>
					Revert
				</button>
			{/if}
		</div>
	{/if}
{/snippet}

<FocusContentShell backHref={entity.detailHref} maxWidth="64rem">
	{#snippet heading()}
		<h1>Edit History</h1>
	{/snippet}

	{#if changesets.length > 0}
		<section class="edit-history">
			<ol class="changeset-list">
				{#each changesets as cs (cs.id)}
					{#if !isEmptyChangeset(cs)}
						<li class="changeset">
							<div class="changeset-header">
								<UserBadge username={cs.user_display} />
								<span class="timestamp"><SmartDate iso={cs.created_at} /></span>
							</div>
							{#if cs.note}
								<p class="changeset-note">{cs.note}</p>
							{/if}
							<dl class="field-list">
								{#each cs.changes as change (change.claim_key)}
									{#if change.is_retracted}
										{@const info =
											change.claim_id != null ? retractionLookup.get(change.claim_id) : undefined}
										<div
											class="field-row field-row-retraction"
											class:field-row-diff={isDiffable(change)}
										>
											<dt>{change.field_name}</dt>
											<dd>
												<span class="reverted-badge">reverted</span>
												{#if info}
													by {#if info.user_display}<a href="/users/{info.user_display}"
															>{info.user_display}</a
														>{:else}system{/if}
													on
													<span class="timestamp"><SmartDate iso={info.created_at} /></span
													>{#if info.note}:
														{info.note}{/if}
												{/if}
											</dd>
											{#if isDiffable(change)}
												<dd>
													<InlineDiff oldValue={change.old_value} newValue={change.new_value} />
												</dd>
											{:else}
												<dd>
													{#if change.old_value !== null && change.old_value !== undefined}
														<span class="old-value">{formatValue(change.old_value)}</span>
														<span class="arrow">&rarr;</span>
													{/if}
													<span class="old-value">{formatValue(change.new_value)}</span>
												</dd>
											{/if}
										</div>
									{:else if isDiffable(change)}
										<div class="field-row field-row-diff">
											<dt>{change.field_name}</dt>
											<dd>
												<InlineDiff oldValue={change.old_value} newValue={change.new_value} />
											</dd>
											{@render revertControls(change)}
										</div>
									{:else}
										<div class="field-row">
											<dt>{change.field_name}</dt>
											<dd>
												{#if change.old_value !== null && change.old_value !== undefined}
													<span class="old-value">{formatValue(change.old_value)}</span>
													<span class="arrow">&rarr;</span>
												{/if}
												<span class="new-value">{formatValue(change.new_value)}</span>
											</dd>
											{@render revertControls(change)}
										</div>
									{/if}
								{/each}
								<!-- Show retractions that couldn't be matched to an original change -->
								{#each cs.retractions ?? [] as retraction (retraction.claim_key)}
									{#if !matchedRetractionIds.has(retraction.claim_id)}
										<div class="field-row field-row-retraction">
											<dt>{retraction.field_name}</dt>
											<dd>
												<span class="reverted-badge">reverted</span>
												<span class="old-value">{formatValue(retraction.old_value)}</span>
											</dd>
										</div>
									{/if}
								{/each}
							</dl>
						</li>
					{/if}
				{/each}
			</ol>
		</section>
	{:else}
		<p class="no-history">No edit history yet.</p>
	{/if}
</FocusContentShell>

<style>
	.changeset-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: var(--size-4);
	}

	.changeset {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-3);
	}

	.changeset-header {
		display: flex;
		align-items: center;
		gap: var(--size-2);
		margin-bottom: var(--size-2);
	}

	.timestamp {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}

	.changeset-note {
		font-size: var(--font-size-0);
		font-style: italic;
		color: var(--color-text-muted);
		margin: 0 0 var(--size-2) 0;
	}

	.field-list {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0;
	}

	.field-row {
		display: flex;
		gap: var(--size-3);
		padding: var(--size-1) 0;
		border-bottom: 1px solid var(--color-border-soft);
		font-size: var(--font-size-0);
		flex-wrap: wrap;
	}

	.field-row:last-child {
		border-bottom: none;
	}

	.field-row dt {
		min-width: 10rem;
		font-weight: 500;
		color: var(--color-text-muted);
	}

	.field-row dd {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--size-1);
		color: var(--color-text-primary);
		word-break: break-word;
		flex: 1;
	}

	.field-row-diff {
		flex-wrap: wrap;
	}

	.field-row-diff dd {
		flex-basis: 100%;
		display: block;
	}

	.old-value {
		text-decoration: line-through;
		opacity: 0.5;
	}

	.arrow {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.new-value {
		font-weight: 500;
	}

	.no-history {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	/* Revert controls */
	.revert-cell {
		margin-left: auto;
		flex-shrink: 0;
	}

	.btn-revert {
		font-size: var(--font-size-00, 0.75rem);
		padding: 0.15em 0.5em;
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-1);
		background: transparent;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.btn-revert:hover {
		border-color: var(--color-danger);
		color: var(--color-danger);
	}

	.btn-revert-dim {
		opacity: 0.5;
	}

	.revert-form {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
		padding: var(--size-1) 0;
	}

	.revert-input {
		font-size: var(--font-size-0);
		padding: var(--size-1);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-1);
		width: 100%;
		min-width: 16rem;
	}

	.revert-actions {
		display: flex;
		gap: var(--size-1);
	}

	.btn-revert-submit {
		font-size: var(--font-size-00, 0.75rem);
		padding: 0.25em 0.75em;
		border: 1px solid var(--color-danger);
		border-radius: var(--radius-1);
		background: var(--color-danger);
		color: white;
		cursor: pointer;
	}

	.btn-revert-submit:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-revert-cancel {
		font-size: var(--font-size-00, 0.75rem);
		padding: 0.25em 0.75em;
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-1);
		background: transparent;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.revert-error {
		font-size: var(--font-size-00, 0.75rem);
		color: var(--color-danger);
		margin: 0;
	}

	/* Retraction rows */
	.field-row-retraction {
		opacity: 0.6;
	}

	.reverted-badge {
		font-size: var(--font-size-00, 0.75rem);
		padding: 0.1em 0.4em;
		border-radius: var(--radius-1);
		background: var(--color-danger);
		color: white;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}
</style>
