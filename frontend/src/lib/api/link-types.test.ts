import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchLinkTypes, searchLinkTargets, _resetCache } from './link-types';

const MOCK_TYPES = [
	{ name: 'title', label: 'Title', description: 'Link to a title', flow: 'standard' as const },
	{
		name: 'manufacturer',
		label: 'Manufacturer',
		description: 'Link to a manufacturer',
		flow: 'standard' as const
	}
];

const MOCK_TARGETS = {
	results: [{ ref: 'williams', label: 'Williams' }]
};

beforeEach(() => {
	_resetCache();
	vi.restoreAllMocks();
});

afterEach(() => {
	_resetCache();
});

function mockFetch(body: unknown, ok = true, status = 200) {
	return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
		ok,
		status,
		json: () => Promise.resolve(body)
	} as Response);
}

describe('fetchLinkTypes', () => {
	it('fetches from API on first call', async () => {
		const spy = mockFetch(MOCK_TYPES);
		const result = await fetchLinkTypes();
		expect(result).toEqual(MOCK_TYPES);
		expect(spy).toHaveBeenCalledOnce();
		expect(spy).toHaveBeenCalledWith('/api/link-types/');
	});

	it('returns cached result on second call without fetching', async () => {
		const spy = mockFetch(MOCK_TYPES);
		await fetchLinkTypes();
		const result = await fetchLinkTypes();
		expect(result).toEqual(MOCK_TYPES);
		expect(spy).toHaveBeenCalledOnce();
	});

	it('throws on non-ok response', async () => {
		mockFetch(null, false, 500);
		await expect(fetchLinkTypes()).rejects.toThrow('Failed to fetch link types: 500');
	});
});

describe('searchLinkTargets', () => {
	it('fetches with type and query params', async () => {
		const spy = mockFetch(MOCK_TARGETS);
		const result = await searchLinkTargets('manufacturer', 'wil');
		expect(result).toEqual(MOCK_TARGETS);
		expect(spy).toHaveBeenCalledWith('/api/link-types/targets/?type=manufacturer&q=wil');
	});

	it('encodes query parameter', async () => {
		const spy = mockFetch(MOCK_TARGETS);
		await searchLinkTargets('title', 'hello world');
		expect(spy).toHaveBeenCalledWith('/api/link-types/targets/?type=title&q=hello+world');
	});

	it('throws on non-ok response', async () => {
		mockFetch(null, false, 400);
		await expect(searchLinkTargets('invalid', '')).rejects.toThrow(
			'Failed to search link targets: 400'
		);
	});
});
