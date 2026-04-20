<script lang="ts">
	import { resolve } from '$app/paths';

	type RelatedTitleLink = {
		relation: string;
		other_title: { name: string; slug: string };
		source_model: { name: string; slug: string };
	};

	let { relatedTitles }: { relatedTitles: RelatedTitleLink[] } = $props();

	function label(relation: string): string {
		if (relation === 'remake_of') return 'is a remake of';
		if (relation === 'converted_from') return 'was converted from';
		return relation;
	}
</script>

<ul class="related-titles">
	{#each relatedTitles as link (`${link.source_model.slug}-${link.relation}-${link.other_title.slug}`)}
		<li>
			<span class="source">{link.source_model.name}</span>
			<span class="relation">{label(link.relation)}</span>
			<a href={resolve(`/titles/${link.other_title.slug}`)}>{link.other_title.name}</a>
		</li>
	{/each}
</ul>

<style>
	.related-titles {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--size-2);
	}

	.source {
		font-weight: 500;
	}

	.relation {
		color: var(--color-text-muted);
		margin: 0 var(--size-1);
	}
</style>
