import * as Sentry from '@sentry/sveltekit';
import client, { registerOnPolicyDenied } from '$lib/api/client';
import type { Activity } from '$lib/api/schema';

interface AuthState {
  isAuthenticated: boolean;
  id: number | null;
  username: string | null;
  firstName: string;
  lastName: string;
  // `Partial` rather than `Record` because keys may be missing during
  // the cold-start window before `load()` resolves and during brief
  // deploy skew (a new activity registered server-side before the SPA
  // bundle has caught up). `can()` collapses missing → `false`.
  capabilities: Partial<Record<Activity, boolean>>;
}

const ANONYMOUS: AuthState = {
  isAuthenticated: false,
  id: null,
  username: null,
  firstName: '',
  lastName: '',
  capabilities: {},
};

function createAuthStore() {
  let state = $state<AuthState>({ ...ANONYMOUS });
  let loaded = $state(false);
  // De-dupe concurrent refreshes: a burst of `policy_denied` 403s on
  // a list page would otherwise fire N parallel /me/ round-trips.
  let inflight: Promise<void> | null = null;

  function set(data: {
    is_authenticated: boolean;
    id?: number | null;
    username?: string | null;
    first_name?: string;
    last_name?: string;
    capabilities?: { [key: string]: boolean };
  }) {
    state = {
      isAuthenticated: data.is_authenticated,
      id: data.id ?? null,
      username: data.username ?? null,
      firstName: data.first_name ?? '',
      lastName: data.last_name ?? '',
      capabilities: data.capabilities ?? {},
    };
    loaded = true;
    syncSentryUser(state);
  }

  /**
   * Mirror auth state into Sentry's browser scope.
   *
   * **Privacy chokepoint**: we send `{id, username}` and nothing else.
   * There is no `beforeSend`, so a refactor that adds `email` here ships
   * PII to Sentry. Pinned by tests.
   */
  function syncSentryUser(s: AuthState): void {
    // `set()` is browser-only today, but auth.svelte.ts is a module
    // singleton and SSR Sentry is also initialized — without this guard a
    // future SSR caller would attach user data to a per-request scope that
    // survives across requests. Mirrors the registerOnPolicyDenied guard.
    if (typeof window === 'undefined') return;
    // Skip in dev/CI/tests where the SDK was never init'd.
    if (!Sentry.isInitialized()) return;
    if (s.isAuthenticated && s.id !== null && s.username !== null) {
      Sentry.setUser({ id: s.id, username: s.username });
      Sentry.setTag('auth_state', 'auth');
    } else {
      Sentry.setUser(null);
      Sentry.setTag('auth_state', 'anon');
    }
  }

  async function load() {
    if (loaded) return;
    const { data } = await client.GET('/api/auth/me/');
    if (data) set(data);
  }

  async function refresh(): Promise<void> {
    if (inflight) return inflight;
    inflight = (async () => {
      try {
        const { data } = await client.GET('/api/auth/me/');
        if (data) set(data);
      } finally {
        inflight = null;
      }
    })();
    return inflight;
  }

  async function logout() {
    const { data } = await client.POST('/api/auth/logout/');
    if (data) set(data);
  }

  function can(activity: Activity): boolean {
    // Default-deny: anything not literally `true` (missing key,
    // `undefined`, malformed value) is denied.
    return state.capabilities[activity] === true;
  }

  function _resetForTest(): void {
    // The auth store is a module singleton; tests inherit each
    // other's `state` and `loaded` flag without an explicit reset.
    // Tests should call this in `beforeEach` to start from a clean
    // anonymous baseline. Mirrors `toast._resetForTest()`.
    state = { ...ANONYMOUS };
    loaded = false;
    inflight = null;
  }

  return {
    get isAuthenticated() {
      return state.isAuthenticated;
    },
    get id() {
      return state.id;
    },
    get username() {
      return state.username;
    },
    get firstName() {
      return state.firstName;
    },
    get lastName() {
      return state.lastName;
    },
    get loaded() {
      return loaded;
    },
    load,
    refresh,
    logout,
    can,
    _resetForTest,
  };
}

export const auth = createAuthStore();

// Wire the 403-as-invalidation hook (registration callback, not a
// direct import — see client.ts for why). Browser-only: `client.ts`'s
// `onPolicyDenied` slot is never invoked SSR because no SSR code
// imports this module.
if (typeof window !== 'undefined') {
  registerOnPolicyDenied(() => {
    void auth.refresh();
  });
}
