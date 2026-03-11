<script lang="ts">
	import { resolve } from '$app/paths';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
</script>

<svelte:head>
	<title>{SITE_NAME}</title>
</svelte:head>

<div class="home">
	<section class="intro">
		<p>
			Pinball is not a relic. It is a living art form — part engineering marvel, part arcade
			theater, part competitive sport — and it has never stopped evolving. While the world chased
			pixels, pinball kept doing what no screen can: putting a steel ball under real gravity,
			launching it into a world of ramps, targets, and mechanical surprise, and daring you to keep
			it alive.
		</p>
	</section>

	<section class="content-block">
		<h2>A Game That Refuses to Die</h2>
		<p>
			<a href={resolveHref('/manufacturers/stern-pinball')}>Stern Pinball</a> releases a half-dozen
			new titles every year, and today the majority of machines go to private collectors rather than
			arcades. Meanwhile, upstarts like
			<a href={resolveHref('/manufacturers/jersey-jack')}>Jersey Jack Pinball</a>
			and <a href={resolveHref('/manufacturers/american-pinball')}>American Pinball</a> are pushing the
			form forward with larger-than-life LCD displays, innovative toy mechanisms, and gameplay ideas the
			old guard never imagined. Boutique builders craft limited-run machines for devoted players, and
			a growing DIY community designs and builds original tables from scratch.
		</p>
		<p>
			Competitive pinball is thriving too. The
			<a href="https://www.ifpapinball.com/">International Flipper Pinball Association</a> tracks thousands
			of ranked players worldwide, and major tournaments draw crowds and prize pools that would have been
			unthinkable a generation ago. Pinball bars and lounges have become fixtures of city nightlife from
			Portland to Berlin.
		</p>
	</section>

	<section class="content-block">
		<h2>Every Machine Tells a Story</h2>
		<p>
			A pinball machine is a collaboration between artists, engineers, and storytellers. The
			playfield designer sets the geometry — the angles that make a shot feel impossible and then,
			with practice, inevitable. The artist wraps the cabinet in a world: a haunted mansion, a rock
			concert, a deep-space odyssey. The software engineer choreographs the light shows, the music,
			the escalating rules that reward players who dig deeper. And the mechanical engineers build
			the physical magic — spinning discs, rising targets, magnetic ball locks — that no touchscreen
			can replicate.
		</p>
		<p>
			The result is a machine with personality. Players don't just play pinball games — they develop
			relationships with individual tables, learning their rhythms, their quirks, their secrets.
		</p>
	</section>

	<section class="content-block">
		<h2>Explore the Collection</h2>
		<p>
			{SITE_NAME} catalogs the <a href={resolve('/titles')}>machines</a>, the
			<a href={resolve('/manufacturers')}>manufacturers</a>, and the
			<a href={resolve('/people')}>people</a> who have shaped pinball from its earliest coin-operated
			ancestors to today's connected, tournament-ready designs. Browse the archive, discover forgotten
			classics, and trace the lineage of the game that keeps defying the odds.
		</p>
		<nav class="explore-links">
			<a href={resolve('/titles')} class="explore-card">
				<span class="explore-label">Titles</span>
				<span class="explore-desc">Every pinball machine ever made</span>
			</a>
			<a href={resolve('/manufacturers')} class="explore-card">
				<span class="explore-label">Manufacturers</span>
				<span class="explore-desc">The companies behind the games</span>
			</a>
			<a href={resolve('/people')} class="explore-card">
				<span class="explore-label">People</span>
				<span class="explore-desc">Designers, artists, and engineers</span>
			</a>
		</nav>
	</section>
</div>

<style>
	.home {
		padding: var(--size-5) 0;
	}

	.intro {
		max-width: 48rem;
		margin: 0 auto;
		padding: var(--size-4) 0 var(--size-6);
	}

	.intro p {
		font-size: var(--font-size-3);
		line-height: 1.7;
		color: var(--color-text-primary);
	}

	.content-block {
		max-width: 48rem;
		margin: 0 auto;
		padding: var(--size-4) 0;
	}

	.content-block h2 {
		font-size: var(--font-size-5);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.content-block p {
		font-size: var(--font-size-2);
		line-height: 1.7;
		color: var(--color-text-muted);
		margin-bottom: var(--size-3);
	}

	.content-block p:last-of-type {
		margin-bottom: var(--size-4);
	}

	.explore-links {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: var(--size-4);
		margin-top: var(--size-4);
	}

	.explore-card {
		display: flex;
		flex-direction: column;
		padding: var(--size-5);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		text-decoration: none;
		transition:
			border-color 0.15s var(--ease-2),
			box-shadow 0.15s var(--ease-2);
	}

	.explore-card:hover {
		border-color: var(--color-accent);
		box-shadow: 0 2px 8px rgb(0 0 0 / 0.08);
	}

	.explore-label {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-accent);
		margin-bottom: var(--size-1);
	}

	.explore-desc {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}
</style>
