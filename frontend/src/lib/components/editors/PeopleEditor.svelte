<script lang="ts">
	import { untrack } from 'svelte';
	import type { components } from '$lib/api/schema';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import { creditsChanged } from '$lib/edit-helpers';
	import type { EditorDirtyChange } from './editor-contract';
	import {
		EMPTY_EDIT_OPTIONS,
		fetchModelEditOptions,
		type ModelEditOptions
	} from './model-edit-options';
	import { saveModelClaims, type SaveResult, type SaveMeta } from './save-model-claims';

	type Credit = components['schemas']['CreditSchema'];

	let {
		initialCredits,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: {
		initialCredits: Credit[];
		slug: string;
		onsaved: () => void;
		onerror: (message: string) => void;
		ondirtychange?: EditorDirtyChange;
	} = $props();

	type KeyedCredit = { key: number; person_slug: string; role: string };

	let keyCounter = 0;

	function toKeyedCredits(credits: Credit[]): KeyedCredit[] {
		return credits.map((c) => ({
			key: keyCounter++,
			person_slug: c.person.slug,
			role: c.role
		}));
	}

	// untrack: intentional one-time capture; component re-mounts when modal reopens
	const originalCredits = untrack(() => initialCredits);
	let editCredits = $state<KeyedCredit[]>(untrack(() => toKeyedCredits(initialCredits)));
	let dirty = $derived.by(() => {
		const original = originalCredits.map((credit) => `${credit.person.slug}:${credit.role}`);
		const current = editCredits.map((credit) => `${credit.person_slug}:${credit.role}`);
		return JSON.stringify(current) !== JSON.stringify(original);
	});

	let editOptions = $state<ModelEditOptions>(EMPTY_EDIT_OPTIONS);

	$effect(() => {
		fetchModelEditOptions().then((opts) => {
			editOptions = opts;
		});
	});

	$effect(() => {
		ondirtychange(dirty);
	});

	export function isDirty(): boolean {
		return dirty;
	}

	function addCredit() {
		editCredits = [...editCredits, { key: keyCounter++, person_slug: '', role: '' }];
	}

	function removeCredit(index: number) {
		editCredits = editCredits.filter((_, i) => i !== index);
	}

	export async function save(meta?: SaveMeta): Promise<void> {
		const incomplete = editCredits.find(
			(c) => (c.person_slug && !c.role) || (!c.person_slug && c.role)
		);
		if (incomplete) {
			const personLabel = editOptions.people.find((p) => p.slug === incomplete.person_slug)?.label;
			const roleLabel = editOptions.credit_roles.find((r) => r.slug === incomplete.role)?.label;
			if (personLabel) {
				onerror(`${personLabel} is missing a role.`);
			} else if (roleLabel) {
				onerror(`${roleLabel} is missing a person.`);
			} else {
				onerror('Each credit needs both a person and a role.');
			}
			return;
		}

		const cleanCredits = editCredits
			.filter((c) => c.person_slug && c.role)
			.map(({ person_slug, role }) => ({ person_slug, role }));

		if (!creditsChanged(cleanCredits, originalCredits)) {
			onsaved();
			return;
		}

		const result: SaveResult = await saveModelClaims(slug, {
			credits: cleanCredits,
			...meta
		});

		if (result.ok) {
			onsaved();
		} else {
			onerror(result.error);
		}
	}
</script>

<div class="people-editor">
	{#each editCredits as credit, i (credit.key)}
		<div class="credit-row">
			<div class="credit-person">
				<SearchableSelect
					label=""
					options={editOptions.people ?? []}
					bind:selected={editCredits[i].person_slug}
					allowZeroCount
					showCounts={false}
					placeholder="Search people..."
				/>
			</div>
			<div class="credit-role">
				<SearchableSelect
					label=""
					options={editOptions.credit_roles ?? []}
					bind:selected={editCredits[i].role}
					allowZeroCount
					showCounts={false}
					placeholder="Role..."
				/>
			</div>
			<button type="button" class="remove-btn" onclick={() => removeCredit(i)}>&times;</button>
		</div>
	{/each}
	<button
		type="button"
		class="add-btn"
		disabled={editCredits.some((c) => !c.person_slug || !c.role)}
		onclick={addCredit}
	>
		Add credit
	</button>
</div>

<style>
	.people-editor {
		display: flex;
		flex-direction: column;
		gap: var(--size-2);
	}

	.credit-row {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: var(--size-2);
		align-items: end;
	}

	.credit-role {
		width: 10rem;
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
