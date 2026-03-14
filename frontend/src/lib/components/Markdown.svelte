<script lang="ts">
	let { html }: { html: string } = $props();
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitized server-side by nh3 -->
<div>{@html html}</div>

<style>
	div {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		line-height: var(--font-lineheight-3);
	}

	/* Block elements injected by {@html} — need :global since Svelte
	   can't see them at compile time. Scoped to this component's div
	   so they don't leak. */
	div :global(p) {
		margin-bottom: var(--size-3);
	}

	div :global(p:last-child) {
		margin-bottom: 0;
	}

	div :global(a) {
		color: var(--color-link);
		text-decoration: none;
	}

	div :global(a:hover) {
		text-decoration: underline;
	}

	div :global(strong) {
		font-weight: 700;
	}

	div :global(ul),
	div :global(ol) {
		padding-left: var(--size-5);
		margin-bottom: var(--size-3);
	}

	div :global(li) {
		margin-bottom: var(--size-1);
	}

	div :global(blockquote) {
		border-left: 3px solid var(--color-border);
		padding-left: var(--size-4);
		color: var(--color-text-muted);
		margin: 0 0 var(--size-3);
	}

	div :global(code) {
		font-family: var(--font-mono);
		font-size: 0.9em;
		background: var(--color-surface);
		padding: 0.1em 0.3em;
		border-radius: var(--radius-1);
	}

	div :global(pre) {
		background: var(--color-surface);
		padding: var(--size-3);
		border-radius: var(--radius-2);
		overflow-x: auto;
		margin-bottom: var(--size-3);
	}

	div :global(pre code) {
		background: none;
		padding: 0;
	}

	div :global(hr) {
		border: none;
		border-top: 1px solid var(--color-border-soft);
		margin: var(--size-4) 0;
	}

	div :global(table) {
		border-collapse: collapse;
		margin-bottom: var(--size-3);
		width: 100%;
	}

	div :global(th),
	div :global(td) {
		border: 1px solid var(--color-border-soft);
		padding: var(--size-1) var(--size-2);
		text-align: left;
	}

	div :global(th) {
		font-weight: 600;
	}

	div :global(h1),
	div :global(h2),
	div :global(h3),
	div :global(h4),
	div :global(h5),
	div :global(h6) {
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	div :global(.task-list-item) {
		list-style: none;
	}

	div :global(.task-list-item input[type='checkbox']) {
		margin-right: var(--size-1);
	}
</style>
