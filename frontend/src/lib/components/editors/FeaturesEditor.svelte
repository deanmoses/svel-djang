<script lang="ts">
	import { untrack } from 'svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import Fieldset from '$lib/components/form/Fieldset.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import { slugSetChanged } from '$lib/edit-helpers';
	import type { EditorDirtyChange } from './editor-contract';
	import {
		EMPTY_EDIT_OPTIONS,
		fetchModelEditOptions,
		type ModelEditOptions
	} from './model-edit-options';
	import { saveModelClaims, type SaveResult, type SaveMeta } from './save-model-claims';

	type GameplayFeatureRef = { slug: string; name?: string; count?: number | null };

	type FeaturesModel = {
		themes: { slug: string }[];
		tags: { slug: string }[];
		reward_types: { slug: string }[];
		gameplay_features: GameplayFeatureRef[];
	};

	let {
		initialModel,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: {
		initialModel: FeaturesModel;
		slug: string;
		onsaved: () => void;
		onerror: (message: string) => void;
		ondirtychange?: EditorDirtyChange;
	} = $props();

	// Simple M2M fields — stored as slug arrays
	const originalThemes = untrack(() => initialModel.themes);
	const originalTags = untrack(() => initialModel.tags);
	const originalRewardTypes = untrack(() => initialModel.reward_types);

	let themes = $state<string[]>(untrack(() => initialModel.themes.map((t) => t.slug)));
	let tags = $state<string[]>(untrack(() => initialModel.tags.map((t) => t.slug)));
	let rewardTypes = $state<string[]>(untrack(() => initialModel.reward_types.map((t) => t.slug)));

	// Gameplay features — slug + optional count
	type KeyedFeature = { key: number; slug: string; count: string | number };
	let keyCounter = 0;

	function toKeyed(features: GameplayFeatureRef[]): KeyedFeature[] {
		return features.map((f) => ({ key: keyCounter++, slug: f.slug, count: f.count ?? '' }));
	}

	const originalFeatures = untrack(() => initialModel.gameplay_features);
	let features = $state<KeyedFeature[]>(untrack(() => toKeyed(initialModel.gameplay_features)));

	let editOptions = $state<ModelEditOptions>(EMPTY_EDIT_OPTIONS);

	$effect(() => {
		fetchModelEditOptions().then((opts) => {
			editOptions = opts;
		});
	});

	function addFeature() {
		features = [...features, { key: keyCounter++, slug: '', count: '' }];
	}

	function removeFeature(index: number) {
		features = features.filter((_, i) => i !== index);
	}

	function featuresChanged(): boolean {
		const clean = features
			.filter((f) => f.slug)
			.map((f) => `${f.slug}:${f.count}`)
			.sort();
		const orig = originalFeatures.map((f) => `${f.slug}:${f.count ?? ''}`).sort();
		return JSON.stringify(clean) !== JSON.stringify(orig);
	}

	let dirty = $derived.by(
		() =>
			slugSetChanged(themes, originalThemes) ||
			slugSetChanged(tags, originalTags) ||
			slugSetChanged(rewardTypes, originalRewardTypes) ||
			featuresChanged()
	);

	$effect(() => {
		ondirtychange(dirty);
	});

	export function isDirty(): boolean {
		return dirty;
	}

	export async function save(meta?: SaveMeta): Promise<void> {
		const themesChanged = slugSetChanged(themes, originalThemes);
		const tagsChanged = slugSetChanged(tags, originalTags);
		const rewardTypesChanged = slugSetChanged(rewardTypes, originalRewardTypes);
		const gfChanged = featuresChanged();

		if (!dirty) {
			onsaved();
			return;
		}

		const result: SaveResult = await saveModelClaims(slug, {
			themes: themesChanged ? themes : undefined,
			tags: tagsChanged ? tags : undefined,
			reward_types: rewardTypesChanged ? rewardTypes : undefined,
			gameplay_features: gfChanged
				? features
						.filter((f) => f.slug)
						.map((f) => ({
							slug: f.slug,
							count: f.count === '' ? null : Number(f.count)
						}))
				: undefined,
			...meta
		});

		if (result.ok) {
			onsaved();
		} else {
			onerror(result.error);
		}
	}
</script>

<div class="features-editor">
	<div class="features-grid">
		<SearchableSelect
			label="Themes"
			options={editOptions.themes ?? []}
			bind:selected={themes}
			multi
			allowZeroCount
			showCounts={false}
			placeholder="Search themes..."
		/>
		<SearchableSelect
			label="Tags"
			options={editOptions.tags ?? []}
			bind:selected={tags}
			multi
			allowZeroCount
			showCounts={false}
			placeholder="Search tags..."
		/>
		<SearchableSelect
			label="Reward types"
			options={editOptions.reward_types ?? []}
			bind:selected={rewardTypes}
			multi
			allowZeroCount
			showCounts={false}
			placeholder="Search reward types..."
		/>
	</div>

	<Fieldset legend="Gameplay Features">
		<div class="gf-list">
			{#each features as feature, i (feature.key)}
				<div class="gf-row">
					<div class="gf-select">
						<SearchableSelect
							label=""
							options={editOptions.gameplay_features ?? []}
							bind:selected={features[i].slug}
							allowZeroCount
							showCounts={false}
							placeholder="Search features..."
						/>
					</div>
					<div class="gf-count">
						<NumberField label="" bind:value={features[i].count} min={1} />
					</div>
					<button type="button" class="remove-btn" onclick={() => removeFeature(i)}>&times;</button>
				</div>
			{/each}
			<button
				type="button"
				class="add-btn"
				disabled={features.some((f) => !f.slug)}
				onclick={addFeature}
			>
				Add feature
			</button>
		</div>
	</Fieldset>
</div>

<style>
	.features-editor {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}

	.features-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}

	.gf-list {
		display: flex;
		flex-direction: column;
		gap: var(--size-2);
	}

	.gf-row {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: var(--size-2);
		align-items: end;
	}

	.gf-count {
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
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
