<script lang="ts">
	import { resolveHref } from '$lib/utils';

	let { username }: { username: string | null | undefined } = $props();
</script>

{#if username}
	<a href={resolveHref(`/users/${username}`)} class="user-badge">@{username}</a>
{:else}
	<span class="user-badge">system</span>
{/if}

<style>
	.user-badge {
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
		text-decoration: none;
	}

	a.user-badge {
		color: var(--color-accent);
		border-color: var(--color-accent);
	}

	a.user-badge:hover {
		background-color: var(--color-accent);
		color: var(--color-surface);
	}
</style>
