// @vitest-environment jsdom
// jsdom is required so the auth store's `typeof window !== 'undefined'`
// guard runs the module-init `registerOnPolicyDenied(...)` registration —
// the behavior the first two tests pin.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { GET, POST, policyDeniedCallbacks, registerOnPolicyDenied, setUser, setTag, isInitialized } =
  vi.hoisted(() => {
    // The registration happens once, at module-import time, so it can't be
    // asserted through the mock's own call history — that is cleared before
    // every test. Record the callback in a plain array instead.
    const policyDeniedCallbacks: Array<() => void> = [];
    return {
      GET: vi.fn(),
      POST: vi.fn(),
      policyDeniedCallbacks,
      registerOnPolicyDenied: vi.fn((cb: () => void) => {
        policyDeniedCallbacks.push(cb);
      }),
      setUser: vi.fn(),
      setTag: vi.fn(),
      isInitialized: vi.fn(() => true),
    };
  });

vi.mock('$lib/api/client', () => ({
  default: { GET, POST },
  registerOnPolicyDenied,
}));

vi.mock('@sentry/sveltekit', () => ({
  setUser,
  setTag,
  isInitialized,
}));

import { auth } from './auth.svelte';

describe('auth store', () => {
  beforeEach(() => {
    GET.mockReset();
    POST.mockReset();
    setUser.mockReset();
    setTag.mockReset();
    isInitialized.mockReset();
    isInitialized.mockReturnValue(true);
    auth._resetForTest();
  });

  it('registers a 403-as-invalidation callback at module init', () => {
    // The auth store wires `auth.refresh()` into the client's policy-
    // denied hook at import time. If this assertion ever fails, the
    // browser-side 403 invalidation is silently disabled.
    expect(policyDeniedCallbacks).toHaveLength(1);
    expect(policyDeniedCallbacks[0]).toBeTypeOf('function');
  });

  it('the registered callback triggers auth.refresh()', async () => {
    const cb = policyDeniedCallbacks[0];
    expect(cb).toBeDefined();

    const callsBefore = GET.mock.calls.length;
    GET.mockResolvedValueOnce({
      data: { is_authenticated: true, capabilities: {} },
    });
    cb();
    await new Promise((r) => setTimeout(r, 0));
    expect(GET.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  describe('can()', () => {
    it('returns true only when the capability is literally true', async () => {
      GET.mockResolvedValueOnce({
        data: {
          is_authenticated: true,
          capabilities: { 'catalog.edit': true, 'kiosk.edit': false },
        },
      });
      await auth.refresh();

      expect(auth.can('catalog.edit')).toBe(true);
      expect(auth.can('kiosk.edit')).toBe(false);
    });

    it('default-denies missing keys', async () => {
      GET.mockResolvedValueOnce({
        data: { is_authenticated: true, capabilities: { 'catalog.edit': true } },
      });
      await auth.refresh();
      // `kiosk.edit` not present in the response — must default to false.
      expect(auth.can('kiosk.edit')).toBe(false);
    });
  });

  describe('refresh()', () => {
    it('re-fetches /me/ even when the store is already loaded', async () => {
      // First call populates the store and flips `loaded` to true.
      GET.mockResolvedValueOnce({
        data: { is_authenticated: true, capabilities: { 'catalog.edit': true } },
      });
      await auth.refresh();
      expect(auth.can('catalog.edit')).toBe(true);
      expect(auth.loaded).toBe(true);

      // Second call must still hit /me/ (unlike `load()`, which gates
      // on `loaded`) and replace the capability map.
      const beforeRefreshCalls = GET.mock.calls.length;
      GET.mockResolvedValueOnce({
        data: { is_authenticated: true, capabilities: { 'catalog.edit': false } },
      });
      await auth.refresh();

      expect(GET.mock.calls.length).toBeGreaterThan(beforeRefreshCalls);
      expect(auth.can('catalog.edit')).toBe(false);
    });

    it('attributes authenticated users to Sentry with exactly {id, username}', async () => {
      // Pins the privacy chokepoint: the keep-list must stay {id, username}.
      // A refactor that adds `email` (or any other field) fails this test.
      GET.mockResolvedValueOnce({
        data: {
          is_authenticated: true,
          id: 42,
          username: 'pinwizard',
          first_name: 'Pin',
          last_name: 'Wizard',
          capabilities: {},
        },
      });
      await auth.refresh();

      expect(setUser).toHaveBeenCalledTimes(1);
      expect(setUser).toHaveBeenCalledWith({ id: 42, username: 'pinwizard' });
      expect(setTag).toHaveBeenCalledWith('auth_state', 'auth');
    });

    it('de-dupes concurrent calls', async () => {
      let resolveGet: (v: { data: unknown }) => void = () => {};
      const pending = new Promise<{ data: unknown }>((r) => {
        resolveGet = r;
      });
      GET.mockReturnValueOnce(pending);

      const a = auth.refresh();
      const b = auth.refresh();
      const c = auth.refresh();

      // Only one network call until the in-flight promise resolves.
      expect(GET).toHaveBeenCalledTimes(1);

      resolveGet({
        data: { is_authenticated: true, capabilities: { 'catalog.edit': true } },
      });
      await Promise.all([a, b, c]);

      expect(GET).toHaveBeenCalledTimes(1);
    });
  });

  describe('logout()', () => {
    it('clears the Sentry user and tags the scope anonymous', async () => {
      // Seed the scope as authenticated first so the logout transition
      // is observable.
      GET.mockResolvedValueOnce({
        data: { is_authenticated: true, id: 1, username: 'me', capabilities: {} },
      });
      await auth.refresh();
      setUser.mockClear();
      setTag.mockClear();

      POST.mockResolvedValueOnce({
        data: { is_authenticated: false, capabilities: {} },
      });
      await auth.logout();

      expect(setUser).toHaveBeenCalledTimes(1);
      expect(setUser).toHaveBeenCalledWith(null);
      expect(setTag).toHaveBeenCalledWith('auth_state', 'anon');
    });
  });

  describe('Sentry guards', () => {
    it('does not touch the Sentry scope when the SDK is not initialized', async () => {
      isInitialized.mockReturnValue(false);
      GET.mockResolvedValueOnce({
        data: { is_authenticated: true, id: 1, username: 'me', capabilities: {} },
      });
      await auth.refresh();

      expect(setUser).not.toHaveBeenCalled();
      expect(setTag).not.toHaveBeenCalled();
    });
  });
});
