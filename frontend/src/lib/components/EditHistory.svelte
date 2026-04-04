<script lang="ts">
	import type { components } from '$lib/api/schema';
	import InlineDiff from './InlineDiff.svelte';
	import UserBadge from './UserBadge.svelte';
	import { isDiffable, formatValue } from './change-display';

	type ChangeSet = components['schemas']['ChangeSetSchema'];

	let { changesets }: { changesets: ChangeSet[] } = $props();

	function formatDate(iso: string): string {
		const d = new Date(iso);
		return d.toLocaleDateString('en', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: 'numeric',
			minute: '2-digit'
		});
	}
</script>

{#if changesets.length > 0}
	<section class="edit-history">
		<h2>Edit History</h2>
		<ol class="changeset-list">
			{#each changesets as cs (cs.id)}
				<li class="changeset">
					<div class="changeset-header">
						<UserBadge username={cs.user_display} />
						<time datetime={cs.created_at}>{formatDate(cs.created_at)}</time>
					</div>
					{#if cs.note}
						<p class="changeset-note">{cs.note}</p>
					{/if}
					<dl class="field-list">
						{#each cs.changes as change (change.claim_key)}
							{#if isDiffable(change)}
								<div class="field-row field-row-diff">
									<dt>{change.field_name}</dt>
									<dd>
										<InlineDiff oldValue={change.old_value} newValue={change.new_value} />
									</dd>
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
								</div>
							{/if}
						{/each}
					</dl>
				</li>
			{/each}
		</ol>
	</section>
{:else}
	<p class="no-history">No edit history yet.</p>
{/if}

<style>
	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

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

	time {
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
</style>
