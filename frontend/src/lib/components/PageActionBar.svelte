<script lang="ts">
  import EditSectionMenu from '$lib/components/EditSectionMenu.svelte';
  import type { EditSectionDropdown, EditSectionMenuItem } from '$lib/components/edit-section-menu';
  import ActionMenu from '$lib/components/ActionMenu.svelte';

  type Props = {
    detailHref?: string;
    editHref?: string;
    editSections?: EditSectionMenuItem[];
    /** Multiple labeled edit dropdowns (e.g. single-model title: "Edit Title" + "Edit Model"). Supersedes editSections/editHref. */
    editDropdowns?: EditSectionDropdown[];
    historyHref?: string;
    sourcesHref?: string;
  };

  let {
    detailHref,
    editHref,
    editSections = [],
    editDropdowns,
    historyHref,
    sourcesHref,
  }: Props = $props();
</script>

<nav aria-label="Page actions">
  {#if detailHref}
    <a class="detail-link" href={detailHref}>Back</a>
  {/if}
  <div class="actions">
    {#if editDropdowns && editDropdowns.length > 0}
      {#each editDropdowns as dropdown (dropdown.label)}
        <EditSectionMenu label={dropdown.label} items={dropdown.items} />
      {/each}
    {:else if editSections.length > 0}
      <EditSectionMenu items={editSections} />
    {:else if editHref}
      <a href={editHref}>Edit</a>
    {/if}
    {#if historyHref}
      <a href={historyHref}>History</a>
    {/if}
    {#if sourcesHref}
      <ActionMenu label="Tools">
        <a class="tools-item" href={sourcesHref} role="menuitem">Sources</a>
      </ActionMenu>
    {/if}
  </div>
</nav>

<style>
  nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--size-4);
    padding: var(--size-2) 0 var(--size-3);
    border-bottom: 1px solid var(--color-border-soft);
    margin-bottom: var(--size-4);
  }

  .actions {
    display: flex;
    align-items: baseline;
    gap: var(--size-4);
    margin-left: auto;
  }

  .detail-link::before {
    content: '← ';
  }

  nav a {
    color: var(--color-text-muted);
    text-decoration: none;
    font-size: var(--font-size-0);
  }

  nav a:hover {
    color: var(--color-accent);
  }

  .tools-item {
    display: block;
    padding: var(--size-1) var(--size-3);
    font-size: var(--font-size-0);
    outline-offset: -2px;
  }

  .tools-item:hover {
    color: var(--color-accent);
    background: var(--color-surface);
  }

  .tools-item:focus-visible {
    outline: 2px solid var(--color-accent);
  }
</style>
