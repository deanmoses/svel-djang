<script lang="ts">
	import { resolve } from '$app/paths';
	import type { components } from '$lib/api/schema';

	type Credit = components['schemas']['DesignCreditSchema'];

	let { credits }: { credits: Credit[] } = $props();
</script>

{#if credits.length > 0}
	<section class="credits">
		<h2>Credits</h2>
		<ul>
			{#each credits as credit (credit.person_slug + credit.role)}
				<li>
					<a href={resolve(`/people/${credit.person_slug}`)}>{credit.person_name}</a>
					<span class="role">{credit.role_display}</span>
				</li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	section {
		margin-bottom: var(--size-6);
	}

	ul {
		list-style: none;
		padding: 0;
	}

	li {
		display: flex;
		justify-content: space-between;
		padding: var(--size-2) 0;
		border-bottom: 1px solid var(--color-border-soft);
		font-size: var(--font-size-1);
	}

	.role {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}
</style>
