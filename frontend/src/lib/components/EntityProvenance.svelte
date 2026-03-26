<script lang="ts">
	import type { components } from '$lib/api/schema';

	type Claim = components['schemas']['ClaimSchema'];
	type FieldGroup = { field: string; claims: Claim[] };

	let { activity }: { activity: Claim[] } = $props();

	let activityGroups = $derived.by(() => {
		const byField: Record<string, Claim[]> = {};
		for (const claim of activity) {
			(byField[claim.field_name] ??= []).push(claim);
		}

		const conflicts: FieldGroup[] = [];
		const agreed: FieldGroup[] = [];
		const single: FieldGroup[] = [];

		for (const [field, claims] of Object.entries(byField)) {
			const group = { field, claims };
			if (claims.length === 1) {
				single.push(group);
			} else {
				const values = claims.map((c) => JSON.stringify(c.value));
				const allSame = values.every((v) => v === values[0]);
				if (allSame) agreed.push(group);
				else conflicts.push(group);
			}
		}

		return { conflicts, agreed, single };
	});

	function claimAttribution(claim: Claim): string {
		return claim.source_name ?? (claim.user_display ? `@${claim.user_display}` : 'Unknown');
	}

	function formatValue(v: unknown): string {
		const s = typeof v === 'string' ? v : JSON.stringify(v);
		return s.length > 100 ? s.slice(0, 100) + '...' : s;
	}
</script>

{#if activity.length > 0}
	{@const { conflicts, agreed, single } = activityGroups}
	{@const contributorNames = [
		...new Set(
			activity
				.map((c) => c.source_name ?? (c.user_display ? `@${c.user_display}` : null))
				.filter(Boolean)
		)
	]}
	<section class="activity">
		<h2>Sources</h2>
		<p class="activity-summary">
			{contributorNames.join(' and ')} contributed to this record.
		</p>

		{#if conflicts.length > 0}
			<details class="activity-group" open>
				<summary>
					<h3>
						Conflicts resolved ({conflicts.length} field{conflicts.length === 1 ? '' : 's'})
					</h3>
				</summary>
				<dl class="field-list">
					{#each conflicts as { field, claims } (field)}
						<div class="field-row conflict">
							<dt>{field}</dt>
							<dd>
								{#each claims as claim, i (i)}
									<span class="claim" class:used={claim.is_winner}>
										<span class="source-badge">{claimAttribution(claim)}</span>
										{formatValue(claim.value)}
										{#if claim.is_winner}
											<span class="badge-used">used</span>
										{/if}
										{#if claim.changeset_note}
											<span class="changeset-note">{claim.changeset_note}</span>
										{/if}
									</span>
								{/each}
							</dd>
						</div>
					{/each}
				</dl>
			</details>
		{/if}

		{#if agreed.length > 0}
			<details class="activity-group">
				<summary>
					<h3>Sources agree ({agreed.length} field{agreed.length === 1 ? '' : 's'})</h3>
				</summary>
				<dl class="field-list">
					{#each agreed as { field, claims } (field)}
						<div class="field-row">
							<dt>{field}</dt>
							<dd>
								<span class="claim used">
									{formatValue(claims[0].value)}
									<span class="source-list">
										{claims.map(claimAttribution).join(', ')}
									</span>
									{#if claims[0].changeset_note}
										<span class="changeset-note">{claims[0].changeset_note}</span>
									{/if}
								</span>
							</dd>
						</div>
					{/each}
				</dl>
			</details>
		{/if}

		{#if single.length > 0}
			<details class="activity-group">
				<summary>
					<h3>Single source ({single.length} field{single.length === 1 ? '' : 's'})</h3>
				</summary>
				<dl class="field-list">
					{#each single as { field, claims } (field)}
						<div class="field-row">
							<dt>{field}</dt>
							<dd>
								<span class="claim used">
									<span class="source-badge">{claimAttribution(claims[0])}</span>
									{formatValue(claims[0].value)}
									{#if claims[0].changeset_note}
										<span class="changeset-note">{claims[0].changeset_note}</span>
									{/if}
								</span>
							</dd>
						</div>
					{/each}
				</dl>
			</details>
		{/if}
	</section>
{:else}
	<p class="no-activity">No source data recorded yet.</p>
{/if}

<style>
	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.activity-summary {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		margin-bottom: var(--size-4);
	}

	.activity-group {
		margin-bottom: var(--size-4);
	}

	.activity-group h3 {
		font-size: var(--font-size-1);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.activity-group summary {
		cursor: pointer;
		list-style: revert;
	}

	.activity-group summary h3 {
		display: inline;
	}

	.field-list {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0;
	}

	.field-row {
		display: flex;
		gap: var(--size-3);
		padding: var(--size-2) 0;
		border-bottom: 1px solid var(--color-border-soft);
		font-size: var(--font-size-0);
	}

	.field-row dt {
		min-width: 10rem;
		font-weight: 500;
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.field-row dd {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
		font-size: var(--font-size-0);
		color: var(--color-text-primary);
		word-break: break-word;
	}

	.claim {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--size-2);
		opacity: 0.5;
	}

	.claim.used {
		opacity: 1;
	}

	.source-badge {
		display: inline-block;
		padding: 1px var(--size-2);
		font-size: var(--font-size-00, 0.7rem);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		border-radius: var(--radius-1);
		background-color: var(--color-surface);
		border: 1px solid var(--color-border-soft);
		color: var(--color-text-muted);
	}

	.badge-used {
		font-size: var(--font-size-00, 0.7rem);
		font-weight: 600;
		color: var(--color-accent);
	}

	.changeset-note {
		width: 100%;
		font-size: var(--font-size-00, 0.7rem);
		font-style: italic;
		color: var(--color-text-muted);
	}

	.source-list {
		font-size: var(--font-size-00, 0.7rem);
		color: var(--color-text-muted);
	}

	.no-activity {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}
</style>
