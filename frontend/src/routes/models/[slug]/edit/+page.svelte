<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import { resolveHref } from '$lib/utils';
	import client from '$lib/api/client';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import TagInput from '$lib/components/form/TagInput.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import TextAreaField from '$lib/components/form/TextAreaField.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import MonthSelect from '$lib/components/form/MonthSelect.svelte';
	import { buildModelPatchBody, modelToFormFields } from './model-edit';

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

	// --- Edit options (single batch fetch) ---

	type OptionItem = { slug: string; label: string; count: number };
	type EditOptions = Record<string, OptionItem[]>;

	let editOptions = $state<EditOptions>({});

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
		const body = buildModelPatchBody(
			{
				fields: editFields,
				themes: selectedThemes,
				tags: selectedTags,
				rewardTypes: selectedRewardTypes,
				gameplayFeatures: editGameplayFeatures,
				credits: editCredits,
				abbreviations: editAbbreviations,
				note: editNote
			},
			model
		);

		if (!body) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/models/{slug}/claims/', {
			params: { path: { slug: model.slug } },
			body
		});

		if (updated) {
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

<EditFormShell {saveStatus} {saveError} onsave={saveChanges}>
	{#if model.title && model.title_models.length <= 1}
		<section class="merged-note">
			<h3>Merged Single-Model View</h3>
			<p>
				This title has one model, and the public detail page merges title and model information. You
				are editing model-owned facts here.
			</p>
			<div class="merged-actions">
				<a href={resolveHref(`/titles/${model.title.slug}/edit`)}>Edit title facts</a>
				<a href={resolveHref(`/titles/${model.title.slug}/activity`)}>Title activity</a>
			</div>
		</section>
	{/if}

	<!-- Identity -->
	<TextField label="Name" bind:value={editFields.name} />
	<TextAreaField label="Description" bind:value={editFields.description} rows={6} />

	<!-- Date -->
	<fieldset class="field-group">
		<legend>Date</legend>
		<div class="date-row">
			<NumberField label="Year" bind:value={editFields.year} min={1800} max={2100} />
			<MonthSelect label="Month" bind:value={editFields.month} />
		</div>
	</fieldset>

	<!-- Classification -->
	<fieldset class="field-group">
		<legend>Classification</legend>
		<div class="classification-grid">
			<SearchableSelect
				label="Corporate entity"
				options={editOptions.corporate_entities ?? []}
				bind:selected={editFields.corporate_entity}
				allowZeroCount
				placeholder="Search corporate entities..."
			/>
			<SearchableSelect
				label="Technology generation"
				options={editOptions.technology_generations ?? []}
				bind:selected={editFields.technology_generation}
				allowZeroCount
				placeholder="Search generations..."
			/>
			<SearchableSelect
				label="Technology subgeneration"
				options={editOptions.technology_subgenerations ?? []}
				bind:selected={editFields.technology_subgeneration}
				allowZeroCount
				placeholder="Search subgenerations..."
			/>
			<SearchableSelect
				label="Display type"
				options={editOptions.display_types ?? []}
				bind:selected={editFields.display_type}
				allowZeroCount
				placeholder="Search display types..."
			/>
			<SearchableSelect
				label="Display subtype"
				options={editOptions.display_subtypes ?? []}
				bind:selected={editFields.display_subtype}
				allowZeroCount
				placeholder="Search display subtypes..."
			/>
			<SearchableSelect
				label="Cabinet"
				options={editOptions.cabinets ?? []}
				bind:selected={editFields.cabinet}
				allowZeroCount
				placeholder="Search cabinets..."
			/>
			<SearchableSelect
				label="Game format"
				options={editOptions.game_formats ?? []}
				bind:selected={editFields.game_format}
				allowZeroCount
				placeholder="Search game formats..."
			/>
			<SearchableSelect
				label="System"
				options={editOptions.systems ?? []}
				bind:selected={editFields.system}
				allowZeroCount
				placeholder="Search systems..."
			/>
		</div>
	</fieldset>

	<!-- Specs -->
	<div class="row-2">
		<NumberField label="Players" bind:value={editFields.player_count} min={1} max={8} />
		<NumberField label="Flippers" bind:value={editFields.flipper_count} min={0} max={10} />
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
			<NumberField label="IPDB ID" bind:value={editFields.ipdb_id} min={1} />
			<TextField label="OPDB ID" bind:value={editFields.opdb_id} />
			<NumberField label="Pinside ID" bind:value={editFields.pinside_id} min={1} />
		</div>
	</fieldset>

	<!-- Ratings -->
	<fieldset class="field-group">
		<legend>Ratings</legend>
		<div class="row-2">
			<NumberField
				label="IPDB rating"
				bind:value={editFields.ipdb_rating}
				min={0}
				max={10}
				step={0.01}
			/>
			<NumberField
				label="Pinside rating"
				bind:value={editFields.pinside_rating}
				min={0}
				max={10}
				step={0.01}
			/>
		</div>
	</fieldset>

	<!-- Edit note -->
	<TextField
		label="Edit note"
		bind:value={editNote}
		placeholder="Why are you making this change?"
		optional
	/>
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
