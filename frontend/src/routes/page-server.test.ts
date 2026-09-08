import { describe, expect, it, vi } from 'vitest';
import { isRedirect } from '@sveltejs/kit';
import { load } from './+page.server';

type LoadEvent = Parameters<typeof load>[0];

function makeEvent(modeCookie: string | undefined): LoadEvent {
  return {
    cookies: { get: vi.fn().mockReturnValue(modeCookie) },
  } as unknown as LoadEvent;
}

describe('homepage server load', () => {
  it('redirects to /kiosk when mode=kiosk cookie is set', () => {
    let thrown: unknown;
    try {
      load(makeEvent('kiosk'));
    } catch (err) {
      thrown = err;
    }
    // Rethrow anything that isn't the redirect, so a real fault surfaces as
    // itself rather than as a failed assertion about a redirect.
    if (!isRedirect(thrown)) throw thrown ?? new Error('expected a redirect');
    expect(thrown.status).toBe(307);
    expect(thrown.location).toBe('/kiosk');
  });

  it('returns empty object when no mode cookie', () => {
    expect(load(makeEvent(undefined))).toEqual({});
  });

  it('returns empty object when mode is unknown', () => {
    expect(load(makeEvent('something-else'))).toEqual({});
  });
});
