import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const GET = vi.fn();

vi.mock('$lib/api/client', () => ({
  default: { GET },
}));

const { fetchLinkTypes, searchLinkTargets, _resetCache } = await import('./link-types');

const MOCK_TYPES = [
  { name: 'title', label: 'Title', description: 'Link to a title', flow: 'standard' },
  {
    name: 'manufacturer',
    label: 'Manufacturer',
    description: 'Link to a manufacturer',
    flow: 'standard',
  },
];

const MOCK_TARGETS = {
  results: [{ ref: 'williams', label: 'Williams' }],
};

function ok<T>(data: T) {
  return { data, error: undefined, response: new Response(null, { status: 200 }) };
}

function fail(status: number) {
  return {
    data: undefined,
    error: { detail: 'nope' },
    response: new Response(null, { status }),
  };
}

beforeEach(() => {
  _resetCache();
  GET.mockReset();
});

afterEach(() => {
  _resetCache();
});

describe('fetchLinkTypes', () => {
  it('fetches from API on first call', async () => {
    GET.mockResolvedValue(ok(MOCK_TYPES));
    const result = await fetchLinkTypes();
    expect(result).toEqual(MOCK_TYPES);
    expect(GET).toHaveBeenCalledExactlyOnceWith('/api/link-types/');
  });

  it('returns cached result on second call without fetching', async () => {
    GET.mockResolvedValue(ok(MOCK_TYPES));
    await fetchLinkTypes();
    const result = await fetchLinkTypes();
    expect(result).toEqual(MOCK_TYPES);
    expect(GET).toHaveBeenCalledOnce();
  });

  it('throws on non-ok response', async () => {
    GET.mockResolvedValue(fail(500));
    await expect(fetchLinkTypes()).rejects.toThrow('Failed to fetch link types: 500');
  });
});

describe('searchLinkTargets', () => {
  it('passes type and query as query params', async () => {
    GET.mockResolvedValue(ok(MOCK_TARGETS));
    const result = await searchLinkTargets('manufacturer', 'wil');
    expect(result).toEqual(MOCK_TARGETS);
    expect(GET).toHaveBeenCalledWith('/api/link-types/targets/', {
      params: { query: { type: 'manufacturer', q: 'wil' } },
    });
  });

  it('throws on non-ok response', async () => {
    GET.mockResolvedValue(fail(400));
    await expect(searchLinkTargets('invalid', '')).rejects.toThrow(
      'Failed to search link targets: 400',
    );
  });
});
