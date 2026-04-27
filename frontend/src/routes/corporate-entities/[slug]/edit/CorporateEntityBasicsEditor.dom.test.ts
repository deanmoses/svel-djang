import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CorporateEntityBasicsEditorFixture from './CorporateEntityBasicsEditor.fixture.svelte';

const { PATCH } = vi.hoisted(() => ({
  PATCH: vi.fn(),
}));

const { invalidateAll } = vi.hoisted(() => ({
  invalidateAll: vi.fn(),
}));

const { GET } = vi.hoisted(() => ({
  GET: vi.fn(),
}));

vi.mock('$lib/api/client', () => ({
  default: { PATCH, GET },
}));

vi.mock('$app/navigation', () => ({
  invalidateAll,
}));

describe('CorporateEntityBasicsEditor dirty-state contract', () => {
  beforeEach(() => {
    PATCH.mockReset();
    invalidateAll.mockReset();
    GET.mockReset();
    GET.mockResolvedValue({ data: {}, error: undefined });
  });

  it('reports clean state initially and dirty state after editing', async () => {
    const user = userEvent.setup();
    render(CorporateEntityBasicsEditorFixture);

    expect(screen.getByTestId('dirty-callback')).toHaveTextContent('false');

    await user.click(screen.getByRole('button', { name: 'Check dirty' }));
    expect(screen.getByTestId('dirty-handle')).toHaveTextContent('false');

    await user.clear(screen.getByLabelText('Established'));
    await user.type(screen.getByLabelText('Established'), '1984');

    expect(screen.getByTestId('dirty-callback')).toHaveTextContent('true');

    await user.click(screen.getByRole('button', { name: 'Check dirty' }));
    expect(screen.getByTestId('dirty-handle')).toHaveTextContent('true');
  });

  it('PATCHes cleared nullable year fields as null', async () => {
    PATCH.mockResolvedValueOnce({ data: { slug: 'williams-electronics' }, error: undefined });
    invalidateAll.mockResolvedValue(undefined);

    const user = userEvent.setup();
    render(CorporateEntityBasicsEditorFixture);

    await user.clear(screen.getByLabelText('Established'));
    await user.clear(screen.getByLabelText('Ceased operations'));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(PATCH).toHaveBeenCalledWith('/api/corporate-entities/{public_id}/claims/', {
      params: { path: { public_id: 'williams-electronics' } },
      body: { fields: { year_start: null, year_end: null }, note: '' },
    });
    expect(screen.getByTestId('saved-count')).toHaveTextContent('1');
  });
});
