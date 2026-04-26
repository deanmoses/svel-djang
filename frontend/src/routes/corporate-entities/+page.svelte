<script lang="ts">
  import { resolve } from '$app/paths';
  import client from '$lib/api/client';
  import { createAsyncLoader } from '$lib/async-loader.svelte';
  import Page from '$lib/components/Page.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import StatusMessage from '$lib/components/StatusMessage.svelte';
  import { pageTitle } from '$lib/constants';
  import { formatYearRange } from '$lib/utils';

  const entities = createAsyncLoader(async () => {
    const { data } = await client.GET('/api/corporate-entities/');
    return data ?? [];
  }, []);
</script>

<svelte:head>
  <title>{pageTitle('Corporate Entities')}</title>
</svelte:head>

<Page width="wide">
  <PageHeader title="Corporate Entities" />

  {#if entities.loading}
    <StatusMessage variant="loading">Loading...</StatusMessage>
  {:else if entities.error}
    <StatusMessage variant="error">Failed to load corporate entities.</StatusMessage>
  {:else if entities.data.length === 0}
    <StatusMessage variant="empty">No corporate entities found.</StatusMessage>
  {:else}
    <ul class="entity-list">
      {#each entities.data as entity (entity.slug)}
        <li>
          <a href={resolve(`/corporate-entities/${entity.slug}`)} class="entity-row">
            <span class="entity-name">{entity.name}</span>
            <span class="entity-meta">
              <span class="manufacturer">{entity.manufacturer.name}</span>
              {#if formatYearRange(entity.year_start, entity.year_end)}
                <span class="years">{formatYearRange(entity.year_start, entity.year_end)}</span>
              {/if}
              <span class="count">
                {entity.model_count} model{entity.model_count === 1 ? '' : 's'}
              </span>
            </span>
          </a>
        </li>
      {/each}
    </ul>
  {/if}
</Page>

<style>
  .entity-list {
    list-style: none;
    padding: 0;
  }

  .entity-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: var(--size-3) 0;
    border-bottom: 1px solid var(--color-border-soft);
    text-decoration: none;
    color: inherit;
    gap: var(--size-4);
  }

  .entity-row:hover .entity-name {
    color: var(--color-accent);
  }

  .entity-name {
    font-size: var(--font-size-2);
    color: var(--color-text-primary);
    font-weight: 500;
  }

  .entity-meta {
    display: flex;
    gap: var(--size-4);
    flex-shrink: 0;
    align-items: baseline;
  }

  .manufacturer {
    font-size: var(--font-size-1);
    color: var(--color-text-muted);
  }

  .years {
    font-size: var(--font-size-1);
    color: var(--color-text-muted);
  }

  .count {
    font-size: var(--font-size-1);
    color: var(--color-text-muted);
    min-width: 6rem;
    text-align: right;
  }
</style>
