/**
 * Pure functions for client-side faceted filtering and count computation.
 * No Svelte imports — this module is framework-agnostic and testable.
 */

import { normalizeText } from '$lib/util';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FacetRef {
	slug: string;
	name: string;
}

export interface FacetedTitle {
	name: string;
	slug: string;
	short_name: string;
	machine_count: number;
	manufacturer_name?: string | null;
	manufacturer_slug?: string | null;
	year?: number | null;
	thumbnail_url?: string | null;
	tech_generations: FacetRef[];
	display_types: FacetRef[];
	player_counts: number[];
	systems: FacetRef[];
	themes: FacetRef[];
	persons: FacetRef[];
	franchise?: FacetRef | null;
	series: FacetRef[];
	year_min?: number | null;
	year_max?: number | null;
	ipdb_rating_max?: number | null;
}

export interface FilterState {
	query: string;
	techGeneration: string | null;
	yearMin: number | null;
	yearMax: number | null;
	manufacturer: string | null;
	person: string | null;
	themes: string[];
	displayType: string | null;
	playerCount: number | null;
	system: string | null;
	franchise: string | null;
	series: string | null;
	ratingMin: number | null;
}

export interface FacetCounts {
	techGeneration: Map<string, number>;
	manufacturer: Map<string, number>;
	person: Map<string, number>;
	theme: Map<string, number>;
	displayType: Map<string, number>;
	playerCount: Map<number, number>;
	system: Map<string, number>;
	franchise: Map<string, number>;
	series: Map<string, number>;
}

export function emptyFilterState(): FilterState {
	return {
		query: '',
		techGeneration: null,
		yearMin: null,
		yearMax: null,
		manufacturer: null,
		person: null,
		themes: [],
		displayType: null,
		playerCount: null,
		system: null,
		franchise: null,
		series: null,
		ratingMin: null
	};
}

// ---------------------------------------------------------------------------
// URL <-> FilterState serialization
// ---------------------------------------------------------------------------

/** Param name → how to read it from FilterState */
const PARAM_MAP: {
	param: string;
	get: (f: FilterState) => string | null;
	set: (f: FilterState, v: string) => void;
}[] = [
	{ param: 'q', get: (f) => f.query || null, set: (f, v) => (f.query = v) },
	{ param: 'gen', get: (f) => f.techGeneration, set: (f, v) => (f.techGeneration = v) },
	{
		param: 'ymin',
		get: (f) => (f.yearMin != null ? String(f.yearMin) : null),
		set: (f, v) => (f.yearMin = Number(v))
	},
	{
		param: 'ymax',
		get: (f) => (f.yearMax != null ? String(f.yearMax) : null),
		set: (f, v) => (f.yearMax = Number(v))
	},
	{ param: 'mfr', get: (f) => f.manufacturer, set: (f, v) => (f.manufacturer = v) },
	{ param: 'person', get: (f) => f.person, set: (f, v) => (f.person = v) },
	{
		param: 'theme',
		get: (f) => (f.themes.length > 0 ? f.themes.join(',') : null),
		set: (f, v) => (f.themes = v.split(',').filter(Boolean))
	},
	{ param: 'display', get: (f) => f.displayType, set: (f, v) => (f.displayType = v) },
	{
		param: 'players',
		get: (f) => (f.playerCount != null ? String(f.playerCount) : null),
		set: (f, v) => (f.playerCount = Number(v))
	},
	{ param: 'sys', get: (f) => f.system, set: (f, v) => (f.system = v) },
	{ param: 'franchise', get: (f) => f.franchise, set: (f, v) => (f.franchise = v) },
	{ param: 'series', get: (f) => f.series, set: (f, v) => (f.series = v) },
	{
		param: 'rating',
		get: (f) => (f.ratingMin != null ? String(f.ratingMin) : null),
		set: (f, v) => (f.ratingMin = Number(v))
	}
];

/** Read filter state from URL search params. */
export function filtersFromParams(sp: URLSearchParams): FilterState {
	const f = emptyFilterState();
	for (const { param, set } of PARAM_MAP) {
		const v = sp.get(param);
		if (v != null) set(f, v);
	}
	return f;
}

/** Write filter state to a URLSearchParams (mutates and returns it). */
export function filtersToParams(f: FilterState, sp: URLSearchParams): URLSearchParams {
	for (const { param } of PARAM_MAP) sp.delete(param);
	for (const { param, get } of PARAM_MAP) {
		const v = get(f);
		if (v != null) sp.set(param, v);
	}
	return sp;
}

// ---------------------------------------------------------------------------
// Individual filter predicates
// ---------------------------------------------------------------------------

type Predicate = (t: FacetedTitle) => boolean;

function matchesQuery(t: FacetedTitle, q: string): boolean {
	if (!q) return true;
	return (
		normalizeText(t.name).includes(q) ||
		normalizeText(t.short_name).includes(q) ||
		(t.manufacturer_name != null && normalizeText(t.manufacturer_name).includes(q))
	);
}

function matchesTechGen(t: FacetedTitle, slug: string | null): boolean {
	if (!slug) return true;
	return t.tech_generations.some((tg) => tg.slug === slug);
}

function matchesYear(t: FacetedTitle, ymin: number | null, ymax: number | null): boolean {
	if (ymin == null && ymax == null) return true;
	const tmin = t.year_min ?? t.year;
	const tmax = t.year_max ?? t.year;
	if (tmin == null && tmax == null) return false;
	if (ymin != null && (tmax ?? tmin!) < ymin) return false;
	if (ymax != null && (tmin ?? tmax!) > ymax) return false;
	return true;
}

function matchesManufacturer(t: FacetedTitle, slug: string | null): boolean {
	if (!slug) return true;
	return t.manufacturer_slug === slug;
}

function matchesPerson(t: FacetedTitle, slug: string | null): boolean {
	if (!slug) return true;
	return t.persons.some((p) => p.slug === slug);
}

function matchesThemes(t: FacetedTitle, slugs: string[]): boolean {
	if (slugs.length === 0) return true;
	const titleThemes = new Set(t.themes.map((th) => th.slug));
	return slugs.every((s) => titleThemes.has(s));
}

function matchesDisplayType(t: FacetedTitle, slug: string | null): boolean {
	if (!slug) return true;
	return t.display_types.some((d) => d.slug === slug);
}

function matchesPlayerCount(t: FacetedTitle, count: number | null): boolean {
	if (count == null) return true;
	if (count >= 6) return t.player_counts.some((p) => p >= 6);
	return t.player_counts.includes(count);
}

function matchesSystem(t: FacetedTitle, slug: string | null): boolean {
	if (!slug) return true;
	return t.systems.some((s) => s.slug === slug);
}

function matchesFranchise(t: FacetedTitle, slug: string | null): boolean {
	if (!slug) return true;
	return t.franchise?.slug === slug;
}

function matchesSeries(t: FacetedTitle, slug: string | null): boolean {
	if (!slug) return true;
	return t.series.some((s) => s.slug === slug);
}

function matchesRating(t: FacetedTitle, min: number | null): boolean {
	if (min == null) return true;
	return t.ipdb_rating_max != null && t.ipdb_rating_max >= min;
}

// ---------------------------------------------------------------------------
// Build per-dimension predicates
// ---------------------------------------------------------------------------

interface DimensionPredicates {
	query: Predicate;
	techGeneration: Predicate;
	year: Predicate;
	manufacturer: Predicate;
	person: Predicate;
	themes: Predicate;
	displayType: Predicate;
	playerCount: Predicate;
	system: Predicate;
	franchise: Predicate;
	series: Predicate;
	rating: Predicate;
}

function buildPredicates(state: FilterState): DimensionPredicates {
	const q = normalizeText(state.query.trim());
	return {
		query: (t) => matchesQuery(t, q),
		techGeneration: (t) => matchesTechGen(t, state.techGeneration),
		year: (t) => matchesYear(t, state.yearMin, state.yearMax),
		manufacturer: (t) => matchesManufacturer(t, state.manufacturer),
		person: (t) => matchesPerson(t, state.person),
		themes: (t) => matchesThemes(t, state.themes),
		displayType: (t) => matchesDisplayType(t, state.displayType),
		playerCount: (t) => matchesPlayerCount(t, state.playerCount),
		system: (t) => matchesSystem(t, state.system),
		franchise: (t) => matchesFranchise(t, state.franchise),
		series: (t) => matchesSeries(t, state.series),
		rating: (t) => matchesRating(t, state.ratingMin)
	};
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

export function filterTitles(titles: FacetedTitle[], state: FilterState): FacetedTitle[] {
	const preds = buildPredicates(state);
	const all = Object.values(preds);
	return titles.filter((t) => all.every((p) => p(t)));
}

// ---------------------------------------------------------------------------
// Facet counts (N-1 approach)
// ---------------------------------------------------------------------------

/**
 * For each dimension D, compute the count of each value of D across titles
 * that pass ALL filters EXCEPT D. This gives the correct dynamic counts.
 */
export function computeFacetCounts(titles: FacetedTitle[], state: FilterState): FacetCounts {
	const preds = buildPredicates(state);
	const predKeys = Object.keys(preds) as (keyof DimensionPredicates)[];
	const predValues = Object.values(preds);

	// Compute a bitmask per title: bit i is set if title passes predicate i
	const masks = new Uint16Array(titles.length);
	const allBits = (1 << predKeys.length) - 1;
	for (let ti = 0; ti < titles.length; ti++) {
		let mask = 0;
		for (let pi = 0; pi < predValues.length; pi++) {
			if (predValues[pi](titles[ti])) {
				mask |= 1 << pi;
			}
		}
		masks[ti] = mask;
	}

	// Helper: get index of a dimension key
	const dimIndex = (key: keyof DimensionPredicates) => predKeys.indexOf(key);

	// Helper: count facet values for a dimension, excluding that dimension's filter
	function countFacetRefs(
		dimKey: keyof DimensionPredicates,
		extractor: (t: FacetedTitle) => FacetRef[]
	): Map<string, number> {
		const excludeBit = 1 << dimIndex(dimKey);
		const requiredMask = allBits & ~excludeBit;
		const counts = new Map<string, number>();
		for (let ti = 0; ti < titles.length; ti++) {
			if ((masks[ti] & requiredMask) === requiredMask) {
				for (const ref of extractor(titles[ti])) {
					counts.set(ref.slug, (counts.get(ref.slug) ?? 0) + 1);
				}
			}
		}
		return counts;
	}

	function countSingleRef(
		dimKey: keyof DimensionPredicates,
		extractor: (t: FacetedTitle) => FacetRef | null | undefined
	): Map<string, number> {
		const excludeBit = 1 << dimIndex(dimKey);
		const requiredMask = allBits & ~excludeBit;
		const counts = new Map<string, number>();
		for (let ti = 0; ti < titles.length; ti++) {
			if ((masks[ti] & requiredMask) === requiredMask) {
				const ref = extractor(titles[ti]);
				if (ref) {
					counts.set(ref.slug, (counts.get(ref.slug) ?? 0) + 1);
				}
			}
		}
		return counts;
	}

	function countNumbers(
		dimKey: keyof DimensionPredicates,
		extractor: (t: FacetedTitle) => number[]
	): Map<number, number> {
		const excludeBit = 1 << dimIndex(dimKey);
		const requiredMask = allBits & ~excludeBit;
		const counts = new Map<number, number>();
		for (let ti = 0; ti < titles.length; ti++) {
			if ((masks[ti] & requiredMask) === requiredMask) {
				for (const val of extractor(titles[ti])) {
					counts.set(val, (counts.get(val) ?? 0) + 1);
				}
			}
		}
		return counts;
	}

	return {
		techGeneration: countFacetRefs('techGeneration', (t) => t.tech_generations),
		manufacturer: countSingleRef('manufacturer', (t) =>
			t.manufacturer_slug && t.manufacturer_name
				? { slug: t.manufacturer_slug, name: t.manufacturer_name }
				: null
		),
		person: countFacetRefs('person', (t) => t.persons),
		theme: countFacetRefs('themes', (t) => t.themes),
		displayType: countFacetRefs('displayType', (t) => t.display_types),
		playerCount: countNumbers('playerCount', (t) => t.player_counts),
		system: countFacetRefs('system', (t) => t.systems),
		franchise: countSingleRef('franchise', (t) => t.franchise),
		series: countFacetRefs('series', (t) => t.series)
	};
}

// ---------------------------------------------------------------------------
// Option list builders (extract unique {slug, name} from all titles)
// ---------------------------------------------------------------------------

export interface FacetOption {
	slug: string;
	label: string;
	count: number;
}

export function buildFacetRefOptions(
	titles: FacetedTitle[],
	extractor: (t: FacetedTitle) => FacetRef[],
	counts: Map<string, number>
): FacetOption[] {
	const seen = new Map<string, string>();
	for (const t of titles) {
		for (const ref of extractor(t)) {
			if (!seen.has(ref.slug)) seen.set(ref.slug, ref.name);
		}
	}
	return Array.from(seen.entries()).map(([slug, name]) => ({
		slug,
		label: name,
		count: counts.get(slug) ?? 0
	}));
}

export function buildSingleRefOptions(
	titles: FacetedTitle[],
	extractor: (t: FacetedTitle) => FacetRef | null | undefined,
	counts: Map<string, number>
): FacetOption[] {
	const seen = new Map<string, string>();
	for (const t of titles) {
		const ref = extractor(t);
		if (ref && !seen.has(ref.slug)) seen.set(ref.slug, ref.name);
	}
	return Array.from(seen.entries()).map(([slug, name]) => ({
		slug,
		label: name,
		count: counts.get(slug) ?? 0
	}));
}

// ---------------------------------------------------------------------------
// Active filter label extraction (for removable chip display)
// ---------------------------------------------------------------------------

export interface ActiveFilterLabel {
	/** Unique key for keyed-each, e.g. "techGeneration:solid-state" */
	key: string;
	/** Human-readable label, e.g. "Solid State" */
	label: string;
	/** Which filter field this belongs to (for removal) */
	field: keyof FilterState;
	/** For themes (array field), which specific slug to remove */
	value?: string;
}

export function getActiveFilterLabels(
	filters: FilterState,
	allTitles: FacetedTitle[]
): ActiveFilterLabel[] {
	const labels: ActiveFilterLabel[] = [];

	// Build slug→name lookup maps by scanning allTitles once
	const techGenNames = new Map<string, string>();
	const displayTypeNames = new Map<string, string>();
	const manufacturerNames = new Map<string, string>();
	const personNames = new Map<string, string>();
	const themeNames = new Map<string, string>();
	const systemNames = new Map<string, string>();
	const franchiseNames = new Map<string, string>();
	const seriesNames = new Map<string, string>();

	for (const t of allTitles) {
		for (const ref of t.tech_generations) techGenNames.set(ref.slug, ref.name);
		for (const ref of t.display_types) displayTypeNames.set(ref.slug, ref.name);
		if (t.manufacturer_slug && t.manufacturer_name)
			manufacturerNames.set(t.manufacturer_slug, t.manufacturer_name);
		for (const ref of t.persons) personNames.set(ref.slug, ref.name);
		for (const ref of t.themes) themeNames.set(ref.slug, ref.name);
		for (const ref of t.systems) systemNames.set(ref.slug, ref.name);
		if (t.franchise) franchiseNames.set(t.franchise.slug, t.franchise.name);
		for (const ref of t.series) seriesNames.set(ref.slug, ref.name);
	}

	if (filters.techGeneration) {
		labels.push({
			key: `techGeneration:${filters.techGeneration}`,
			label: techGenNames.get(filters.techGeneration) ?? filters.techGeneration,
			field: 'techGeneration'
		});
	}
	if (filters.displayType) {
		labels.push({
			key: `displayType:${filters.displayType}`,
			label: displayTypeNames.get(filters.displayType) ?? filters.displayType,
			field: 'displayType'
		});
	}
	if (filters.manufacturer) {
		labels.push({
			key: `manufacturer:${filters.manufacturer}`,
			label: manufacturerNames.get(filters.manufacturer) ?? filters.manufacturer,
			field: 'manufacturer'
		});
	}
	if (filters.person) {
		labels.push({
			key: `person:${filters.person}`,
			label: personNames.get(filters.person) ?? filters.person,
			field: 'person'
		});
	}
	for (const slug of filters.themes) {
		labels.push({
			key: `themes:${slug}`,
			label: themeNames.get(slug) ?? slug,
			field: 'themes',
			value: slug
		});
	}
	if (filters.playerCount != null) {
		labels.push({
			key: `playerCount:${filters.playerCount}`,
			label: `${filters.playerCount >= 6 ? '6+' : filters.playerCount} players`,
			field: 'playerCount'
		});
	}
	if (filters.system) {
		labels.push({
			key: `system:${filters.system}`,
			label: systemNames.get(filters.system) ?? filters.system,
			field: 'system'
		});
	}
	if (filters.franchise) {
		labels.push({
			key: `franchise:${filters.franchise}`,
			label: franchiseNames.get(filters.franchise) ?? filters.franchise,
			field: 'franchise'
		});
	}
	if (filters.series) {
		labels.push({
			key: `series:${filters.series}`,
			label: seriesNames.get(filters.series) ?? filters.series,
			field: 'series'
		});
	}
	if (filters.yearMin != null || filters.yearMax != null) {
		const parts: string[] = [];
		if (filters.yearMin != null) parts.push(String(filters.yearMin));
		parts.push('\u2013');
		if (filters.yearMax != null) parts.push(String(filters.yearMax));
		labels.push({
			key: 'year',
			label: `Year: ${parts.join('')}`,
			field: 'yearMin'
		});
	}
	if (filters.ratingMin != null) {
		labels.push({
			key: 'ratingMin',
			label: `Rating \u2265 ${filters.ratingMin}`,
			field: 'ratingMin'
		});
	}

	return labels;
}

export function buildPlayerCountOptions(
	counts: Map<number, number>
): { value: number; label: string; count: number }[] {
	// Group 6+ together
	const grouped = new Map<number, number>();
	for (const [pc, ct] of counts) {
		if (pc >= 6) {
			grouped.set(6, (grouped.get(6) ?? 0) + ct);
		} else {
			grouped.set(pc, (grouped.get(pc) ?? 0) + ct);
		}
	}
	const buckets = [1, 2, 4, 6];
	return buckets.map((v) => ({
		value: v,
		label: v >= 6 ? '6+' : String(v),
		count: grouped.get(v) ?? 0
	}));
}
