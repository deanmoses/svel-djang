<script lang="ts">
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
	import SmartDate from '$lib/components/SmartDate.svelte';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<svelte:head>
	<title>@{profile.username} — {SITE_NAME}</title>
</svelte:head>

<div class="profile-page">
	<header class="profile-header">
		<h1>@{profile.username}</h1>
		<p class="meta">
			Member since {new Date(profile.member_since).toLocaleDateString(undefined, {
				month: 'short',
				year: 'numeric'
			})} · {profile.edit_count}
			{profile.edit_count === 1 ? 'edit' : 'edits'}
		</p>
	</header>

	{#if profile.entities_edited.length > 0}
		<section class="section">
			<h2>Entities edited</h2>
			<ul class="entity-list">
				{#each profile.entities_edited as entity (entity.entity_href)}
					<li class="entity-item">
						<a href={resolveHref(entity.entity_href)} class="entity-link">
							<span class="entity-name">{entity.entity_name}</span>
							<span class="entity-type">{entity.entity_type_label}</span>
						</a>
						<span class="entity-meta">
							{entity.edit_count}
							{entity.edit_count === 1 ? 'edit' : 'edits'} · last
							<SmartDate iso={entity.last_edited_at} />
						</span>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	{#if profile.recent_edits.length > 0}
		<section class="section">
			<h2>Recent edits</h2>
			<ol class="edit-list">
				{#each profile.recent_edits as edit (edit.id)}
					<li class="edit-item">
						<div class="edit-header">
							<a href={resolveHref(edit.entity_href)} class="entity-link">
								<span class="entity-name">{edit.entity_name}</span>
								<span class="entity-type">{edit.entity_type_label}</span>
							</a>
							<span class="timestamp"><SmartDate iso={edit.created_at} /></span>
						</div>
						{#if edit.note}
							<p class="edit-note">{edit.note}</p>
						{/if}
					</li>
				{/each}
			</ol>
		</section>
	{/if}

	{#if profile.entities_edited.length === 0 && profile.recent_edits.length === 0}
		<p class="no-edits">No contributions yet.</p>
	{/if}
</div>

<style>
	.profile-page {
		padding: var(--size-5) 0;
	}

	.profile-header {
		margin-bottom: var(--size-6);
	}

	.profile-header h1 {
		font-size: var(--font-size-5);
		font-weight: 700;
		color: var(--color-text-primary);
		margin: 0 0 var(--size-1) 0;
	}

	.meta {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		margin: 0;
	}

	.section {
		margin-bottom: var(--size-6);
	}

	.section h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.entity-list,
	.edit-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.entity-item,
	.edit-item {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--size-2);
		padding: var(--size-2) 0;
		border-bottom: 1px solid var(--color-border-soft);
	}

	.entity-item:last-child,
	.edit-item:last-child {
		border-bottom: none;
	}

	.entity-link {
		display: inline-flex;
		align-items: baseline;
		gap: var(--size-2);
		text-decoration: none;
		color: var(--color-text-primary);
	}

	.entity-link:hover .entity-name {
		color: var(--color-accent);
	}

	.entity-name {
		font-weight: 500;
	}

	.entity-type {
		font-size: var(--font-size-00, 0.7rem);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-text-muted);
		padding: 1px var(--size-2);
		border-radius: var(--radius-1);
		background-color: var(--color-surface);
		border: 1px solid var(--color-border-soft);
	}

	.entity-meta {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}

	.edit-header {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--size-2);
		width: 100%;
	}

	.timestamp {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		margin-left: auto;
	}

	.edit-note {
		width: 100%;
		font-size: var(--font-size-0);
		font-style: italic;
		color: var(--color-text-muted);
		margin: var(--size-1) 0 0 0;
	}

	.no-edits {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}
</style>
