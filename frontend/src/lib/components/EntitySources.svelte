<script lang="ts">
	import type { components } from '$lib/api/schema';
	import FocusContentShell from './FocusContentShell.svelte';
	import UserBadge from './UserBadge.svelte';
	import SmartDate from './SmartDate.svelte';
	import { getEntityContext } from '$lib/entity-context';
	import { groupSourcesByField } from './entity-provenance';

	type Claim = components['schemas']['ClaimSchema'];
	type CitedChangeSet = components['schemas']['CitedChangeSetSchema'];

	let {
		sources,
		evidence = []
	}: {
		sources: Claim[];
		evidence?: CitedChangeSet[];
	} = $props();

	let sourceGroups = $derived(groupSourcesByField(sources));
	const entity = getEntityContext();

	function claimAttribution(claim: Claim): string {
		return claim.source_name ?? (claim.user_display ? `@${claim.user_display}` : 'Unknown');
	}

	function formatValue(v: unknown): string {
		const s = typeof v === 'string' ? v : JSON.stringify(v);
		return s.length > 100 ? s.slice(0, 100) + '...' : s;
	}
</script>

{#snippet claimDetail(claim: Claim)}
	{#if claim.user_display}
		<UserBadge username={claim.user_display} />
	{:else}
		<span class="source-badge">{claim.source_name ?? 'Unknown'}</span>
	{/if}
	{formatValue(claim.value)}
	{#if claim.is_winner}
		<span class="badge-used">used</span>
	{/if}
	{#if claim.changeset_note}
		<span class="claim-note">{claim.changeset_note}</span>
	{/if}
{/snippet}

<FocusContentShell backHref={entity.detailHref} maxWidth="64rem">
	{#snippet heading()}
		<h1>Sources</h1>
	{/snippet}

	{#if sources.length > 0}
		{@const { conflicts, agreed, single } = sourceGroups}
		{@const contributorNames = [
			...new Set(
				sources
					.map((c) => c.source_name ?? (c.user_display ? `@${c.user_display}` : null))
					.filter(Boolean)
			)
		]}
		<section class="sources">
			{#if evidence.length > 0}
				<section class="evidence">
					<h2>Evidence</h2>
					<ol class="changeset-list">
						{#each evidence as changeset (changeset.id)}
							<li class="changeset-card">
								<div class="changeset-header">
									{#if changeset.user_display}
										<UserBadge username={changeset.user_display} />
									{:else}
										<span class="source-badge">Unknown</span>
									{/if}
									<span class="timestamp"><SmartDate iso={changeset.created_at} /></span>
								</div>
								{#if changeset.note}
									<p class="evidence-note">{changeset.note}</p>
								{/if}
								<p class="changeset-fields">Applies to: {changeset.fields.join(', ')}</p>
								{#each changeset.citations as citation, i (i)}
									<div class="evidence-citation">
										<div class="source-name">{citation.source_name}</div>
										{#if citation.author || citation.year}
											<div class="meta">
												{[citation.author, citation.year].filter(Boolean).join(', ')}
											</div>
										{/if}
										{#if citation.locator}
											<div class="locator">{citation.locator}</div>
										{/if}
										{#if citation.links.length > 0}
											<div class="links">
												{#each citation.links as link (link.url)}
													<a href={link.url} target="_blank" rel="noopener">{link.label}</a>
												{/each}
											</div>
										{/if}
									</div>
								{/each}
							</li>
						{/each}
					</ol>
				</section>
			{/if}

			<p class="sources-summary">
				{contributorNames.join(' and ')} contributed to this record.
			</p>

			{#if conflicts.length > 0}
				<details class="sources-group" open>
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
											{@render claimDetail(claim)}
										</span>
									{/each}
								</dd>
							</div>
						{/each}
					</dl>
				</details>
			{/if}

			{#if agreed.length > 0}
				<details class="sources-group">
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
									</span>
								</dd>
							</div>
						{/each}
					</dl>
				</details>
			{/if}

			{#if single.length > 0}
				<details class="sources-group">
					<summary>
						<h3>Single source ({single.length} field{single.length === 1 ? '' : 's'})</h3>
					</summary>
					<dl class="field-list">
						{#each single as { field, claims } (field)}
							<div class="field-row">
								<dt>{field}</dt>
								<dd>
									<span class="claim used">
										{@render claimDetail(claims[0])}
									</span>
								</dd>
							</div>
						{/each}
					</dl>
				</details>
			{/if}
		</section>
	{:else}
		<p class="no-sources">No source data recorded yet.</p>
	{/if}
</FocusContentShell>

<style>
	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.sources-summary {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		margin-bottom: var(--size-4);
	}

	.evidence {
		margin-bottom: var(--size-5);
	}

	.changeset-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}

	.changeset-card {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-3);
		background: var(--color-surface);
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

	.evidence-note {
		margin: 0 0 var(--size-2);
		font-size: var(--font-size-00, 0.7rem);
		font-style: italic;
		color: var(--color-text-muted);
	}

	.sources-group {
		margin-bottom: var(--size-4);
	}

	.sources-group h3 {
		font-size: var(--font-size-1);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.sources-group summary {
		cursor: pointer;
		list-style: revert;
	}

	.sources-group summary h3 {
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

	.claim-note {
		width: 100%;
		font-size: var(--font-size-00, 0.7rem);
		font-style: italic;
		color: var(--color-text-muted);
	}

	.changeset-fields {
		margin: 0 0 var(--size-2);
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}

	.evidence-citation {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
		padding-top: var(--size-2);
	}

	.links {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-2);
	}

	.links a {
		font-size: var(--font-size-0);
	}

	.source-list {
		font-size: var(--font-size-00, 0.7rem);
		color: var(--color-text-muted);
	}

	.no-sources {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}
</style>
