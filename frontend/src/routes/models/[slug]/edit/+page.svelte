<script lang="ts">
	import { untrack } from 'svelte';
	import { goto, invalidateAll } from '$app/navigation';
	import { resolveHref } from '$lib/utils';
	import client from '$lib/api/client';
	import {
		shouldShowMixedEditCitationWarning,
		type EditCitationSelection,
		withEditMetadata
	} from '$lib/edit-citation';
	import { getEditRedirectHref } from '$lib/edit-routes';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import TagInput from '$lib/components/form/TagInput.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import MonthSelect from '$lib/components/form/MonthSelect.svelte';
	import { fetchFieldConstraints, fc, type FieldConstraints } from '$lib/field-constraints';
	import {
		buildModelPatchBody,
		modelToFormFields,
		TAXONOMY_FK_FIELDS,
		HIERARCHY_FK_FIELDS
	} from './model-edit';

	let { data } = $props();
	let model = $derived(data.model);

	// --- Scalar form state ---

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => modelToFormFields(data.model)));

	// --- Relationship state ---

	let selectedThemes = $state<string[]>(
		untrack(() => model.themes.map((t: { slug: string }) => t.slug))
	);
	let selectedTags = $state<string[]>(
		untrack(() => (model.tags ?? []).map((t: { slug: string }) => t.slug))
	);
	let selectedRewardTypes = $state<string[]>(
		untrack(() => model.reward_types.map((rt: { slug: string }) => rt.slug))
	);
	let featureKeyCounter = $state(0);
	let editGameplayFeatures = $state(
		untrack(() =>
			model.gameplay_features.map((gf) => ({
				key: featureKeyCounter++,
				slug: gf.slug,
				count: gf.count ?? null
			}))
		)
	);
	let creditKeyCounter = $state(0);
	let editCredits = $state(
		untrack(() =>
			model.credits.map((c) => ({
				key: creditKeyCounter++,
				person_slug: c.person.slug,
				role: c.role
			}))
		)
	);
	let editAbbreviations = $state<string[]>(untrack(() => [...model.abbreviations]));
	let editNote = $state('');
	let editCitation = $state<EditCitationSelection | null>(null);
	let pendingBody = $derived(
		buildModelPatchBody(
			{
				fields: editFields,
				themes: selectedThemes,
				tags: selectedTags,
				rewardTypes: selectedRewardTypes,
				gameplayFeatures: editGameplayFeatures,
				credits: editCredits,
				abbreviations: editAbbreviations
			},
			model
		)
	);
	let showMixedEditWarning = $derived(
		shouldShowMixedEditCitationWarning(pendingBody, editCitation)
	);

	// --- Edit options (single batch fetch) ---

	type OptionItem = { slug: string; label: string; count: number };
	type EditOptions = Record<string, OptionItem[]>;

	let editOptions = $state<EditOptions>({});
	let constraints = $state<FieldConstraints>({});

	$effect(() => {
		fetchFieldConstraints('model').then((c) => {
			constraints = c;
		});
	});

	$effect(() => {
		client.GET('/api/models/edit-options/').then(({ data: opts }) => {
			if (opts) {
				const mapped: EditOptions = {};
				for (const [key, items] of Object.entries(opts)) {
					mapped[key] = (items as { slug: string; label: string }[]).map((o) => ({
						slug: o.slug,
						label: o.label,
						count: 0
					}));
				}
				editOptions = mapped;
			}
		});
	});

	// --- Save ---

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	async function saveChanges() {
		const rawBody = pendingBody;
		if (!rawBody) return;
		const body = withEditMetadata(rawBody, editNote, editCitation);

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/models/{slug}/claims/', {
			params: { path: { slug: model.slug } },
			body
		});

		if (updated) {
			const redirectHref = getEditRedirectHref('models', model.slug, updated.slug);
			editFields = modelToFormFields(updated);
			selectedThemes = updated.themes.map((t) => t.slug);
			selectedTags = (updated.tags ?? []).map((t) => t.slug);
			selectedRewardTypes = updated.reward_types.map((rt) => rt.slug);
			editGameplayFeatures = updated.gameplay_features.map((gf) => ({
				key: featureKeyCounter++,
				slug: gf.slug,
				count: gf.count ?? null
			}));
			editCredits = updated.credits.map((c) => ({
				key: creditKeyCounter++,
				person_slug: c.person.slug,
				role: c.role
			}));
			editAbbreviations = [...updated.abbreviations];
			editNote = '';
			editCitation = null;
			if (redirectHref) {
				await goto(redirectHref, { replaceState: true });
				return;
			}
			await invalidateAll();
			saveStatus = 'saved';
			setTimeout(() => (saveStatus = 'idle'), 3000);
		} else {
			saveStatus = 'error';
			saveError = error ? JSON.stringify(error) : 'Save failed.';
		}
	}

	// --- Gameplay feature helpers ---

	function addGameplayFeature() {
		editGameplayFeatures = [
			...editGameplayFeatures,
			{ key: featureKeyCounter++, slug: '', count: null }
		];
	}

	function removeGameplayFeature(index: number) {
		editGameplayFeatures = editGameplayFeatures.filter((_, i) => i !== index);
	}

	// --- Credit helpers ---

	function addCredit() {
		editCredits = [...editCredits, { key: creditKeyCounter++, person_slug: '', role: '' }];
	}

	function removeCredit(index: number) {
		editCredits = editCredits.filter((_, i) => i !== index);
	}
</script>

<EditFormShell
	{saveStatus}
	{saveError}
	onsave={saveChanges}
	bind:note={editNote}
	bind:citation={editCitation}
	{showMixedEditWarning}
>
	{#if model.title && model.title_models.length <= 1}
		<section class="merged-note">
			<h3>Merged Single-Model View</h3>
			<p>
				This title has one model, and the public detail page merges title and model information. You
				are editing model-owned facts here.
			</p>
			<div class="merged-actions">
				<a href={resolveHref(`/titles/${model.title.slug}/edit`)}>Edit title facts</a>
				<a href={resolveHref(`/titles/${model.title.slug}/sources`)}>Title sources</a>
			</div>
		</section>
	{/if}

	<!-- Identity -->
	<TextField label="Name" bind:value={editFields.name} />
	<TextField label="Slug" bind:value={editFields.slug} />
	<MarkdownTextArea label="Description" bind:value={editFields.description} rows={6} />

	<!-- Date -->
	<fieldset class="field-group">
		<legend>Date</legend>
		<div class="date-row">
			<NumberField label="Year" bind:value={editFields.year} {...fc(constraints, 'year')} />
			<MonthSelect label="Month" bind:value={editFields.month} />
		</div>
	</fieldset>

	<!-- Classification -->
	<fieldset class="field-group">
		<legend>Classification</legend>
		<div class="classification-grid">
			{#each TAXONOMY_FK_FIELDS as fk (fk.field)}
				<SearchableSelect
					label={fk.label}
					options={editOptions[fk.optionsKey] ?? []}
					bind:selected={editFields[fk.field]}
					allowZeroCount
					placeholder="Search {fk.label.toLowerCase()}..."
				/>
			{/each}
		</div>
	</fieldset>

	<!-- Hierarchy -->
	<fieldset class="field-group">
		<legend>Hierarchy</legend>
		<div class="classification-grid">
			{#each HIERARCHY_FK_FIELDS as fk (fk.field)}
				<SearchableSelect
					label={fk.label}
					options={(editOptions[fk.optionsKey] ?? []).filter((o) => o.slug !== model.slug)}
					bind:selected={editFields[fk.field]}
					allowZeroCount
					placeholder="Search models..."
				/>
			{/each}
		</div>
	</fieldset>

	<!-- Specs -->
	<div class="row-2">
		<NumberField
			label="Players"
			bind:value={editFields.player_count}
			{...fc(constraints, 'player_count')}
		/>
		<NumberField
			label="Flippers"
			bind:value={editFields.flipper_count}
			{...fc(constraints, 'flipper_count')}
		/>
	</div>
	<NumberField label="Production quantity" bind:value={editFields.production_quantity} min={0} />

	<!-- Themes -->
	<div class="field-group">
		<SearchableSelect
			label="Themes"
			options={editOptions.themes ?? []}
			bind:selected={selectedThemes}
			multi
			allowZeroCount
			placeholder="Search themes..."
		/>
	</div>

	<!-- Gameplay Features -->
	<fieldset class="field-group">
		<legend>Gameplay Features</legend>
		{#each editGameplayFeatures as feat, i (feat.key)}
			<div class="feature-row">
				<div class="feature-select">
					<SearchableSelect
						label=""
						options={(editOptions.gameplay_features ?? []).filter(
							(o) => o.slug === feat.slug || !editGameplayFeatures.some((gf) => gf.slug === o.slug)
						)}
						bind:selected={editGameplayFeatures[i].slug}
						allowZeroCount
						placeholder="Search features..."
					/>
				</div>
				<div class="feature-count">
					<NumberField
						label="Count"
						bind:value={
							() => editGameplayFeatures[i].count ?? '',
							(v) => {
								editGameplayFeatures[i].count =
									v === '' || (typeof v === 'number' && isNaN(v)) ? null : Number(v);
							}
						}
						min={1}
					/>
				</div>
				<button type="button" class="remove-btn" onclick={() => removeGameplayFeature(i)}>
					&times;
				</button>
			</div>
		{/each}
		<button
			type="button"
			class="add-btn"
			disabled={editGameplayFeatures.some((gf) => gf.slug === '')}
			onclick={addGameplayFeature}
		>
			Add feature
		</button>
	</fieldset>

	<!-- Credits -->
	<fieldset class="field-group">
		<legend>Credits</legend>
		{#each editCredits as credit, i (credit.key)}
			<div class="credit-row">
				<div class="credit-person">
					<SearchableSelect
						label=""
						options={editOptions.people ?? []}
						bind:selected={editCredits[i].person_slug}
						allowZeroCount
						placeholder="Search people..."
					/>
				</div>
				<div class="credit-role">
					<SearchableSelect
						label=""
						options={editOptions.credit_roles ?? []}
						bind:selected={editCredits[i].role}
						allowZeroCount
						placeholder="Role..."
					/>
				</div>
				<button type="button" class="remove-btn" onclick={() => removeCredit(i)}> &times; </button>
			</div>
		{/each}
		<button
			type="button"
			class="add-btn"
			disabled={editCredits.some((c) => c.person_slug === '' || c.role === '')}
			onclick={addCredit}
		>
			Add credit
		</button>
	</fieldset>

	<!-- Reward Types -->
	<div class="field-group">
		<SearchableSelect
			label="Reward Types"
			options={editOptions.reward_types ?? []}
			bind:selected={selectedRewardTypes}
			multi
			allowZeroCount
			placeholder="Search reward types..."
		/>
	</div>

	<!-- Tags -->
	<div class="field-group">
		<SearchableSelect
			label="Tags"
			options={editOptions.tags ?? []}
			bind:selected={selectedTags}
			multi
			allowZeroCount
			placeholder="Search tags..."
		/>
	</div>

	<!-- Abbreviations -->
	<TagInput
		label="Abbreviations"
		bind:tags={editAbbreviations}
		placeholder="Type an abbreviation and press Enter"
		optional
	/>

	<!-- Cross-reference IDs -->
	<fieldset class="field-group">
		<legend>Cross-reference IDs</legend>
		<div class="row-3">
			<NumberField
				label="IPDB ID"
				bind:value={editFields.ipdb_id}
				{...fc(constraints, 'ipdb_id')}
			/>
			<TextField label="OPDB ID" bind:value={editFields.opdb_id} />
			<NumberField
				label="Pinside ID"
				bind:value={editFields.pinside_id}
				{...fc(constraints, 'pinside_id')}
			/>
		</div>
	</fieldset>

	<!-- Ratings -->
	<fieldset class="field-group">
		<legend>Ratings</legend>
		<div class="row-2">
			<NumberField
				label="IPDB rating"
				bind:value={editFields.ipdb_rating}
				{...fc(constraints, 'ipdb_rating')}
			/>
			<NumberField
				label="Pinside rating"
				bind:value={editFields.pinside_rating}
				{...fc(constraints, 'pinside_rating')}
			/>
		</div>
	</fieldset>
</EditFormShell>

<style>
	.merged-note,
	.field-group {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-3);
		margin: 0;
	}

	.merged-note {
		margin-bottom: var(--size-4);
	}

	.merged-note h3,
	.field-group > legend {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		padding: 0 var(--size-1);
	}

	.merged-note h3 {
		margin: 0 0 var(--size-2);
	}

	.merged-note p {
		margin: 0 0 var(--size-3);
		color: var(--color-text-muted);
	}

	.merged-actions {
		display: flex;
		gap: var(--size-4);
	}

	.classification-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}

	.date-row,
	.row-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}

	.row-3 {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: var(--size-3);
	}

	/* Credit rows */
	.credit-row {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: var(--size-2);
		align-items: end;
		margin-bottom: var(--size-2);
	}

	.credit-role {
		width: 10rem;
	}

	/* Gameplay feature rows */
	.feature-row {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: var(--size-2);
		align-items: end;
		margin-bottom: var(--size-2);
	}

	.feature-count {
		width: 5rem;
	}

	.remove-btn {
		background: none;
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-1);
		padding: 0.4rem 0.6rem;
		cursor: pointer;
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		line-height: 1;
	}

	.remove-btn:hover {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}

	.add-btn {
		background: none;
		border: 1px dashed var(--color-border-soft);
		border-radius: var(--radius-1);
		padding: var(--size-2) var(--size-3);
		cursor: pointer;
		color: var(--color-text-muted);
		width: 100%;
	}

	.add-btn:hover:not(:disabled) {
		border-color: var(--color-text-muted);
	}

	.add-btn:disabled {
		opacity: 0.4;
		cursor: default;
	}
</style>
