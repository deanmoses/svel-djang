// Public analytics API. Call sites import `analytics` from here and never
// touch the vendor SDK directly — see docs/Analytics.md.
//
// Adapter selection:
//   - dev builds                              → noop
//   - PUBLIC_POSTHOG_KEY missing/blank        → noop (staging/preview/CI without a real key)
//   - SSR (browser=false)                     → noop (keeps server-side analytics.* calls
//                                                from hitting an uninitialized SDK)
//   - otherwise                               → PostHog adapter, initialized once
//
// The key check is a runtime guard, matching the established PUBLIC_SENTRY_DSN
// pattern in hooks.client.ts. The runtime guard is the master switch — note that
// posthog-js itself ships in every production bundle once any call site imports
// `$lib/analytics`, regardless of whether a key is set (locked-down config still
// uses the full SDK; lite SDK is officially de-emphasized).

import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

import type { EventName, EventProperties } from './events';
import { noopAdapter } from './noop';
import { posthogAdapter } from './posthog';

export interface Analytics {
  pageview: (path: string) => void;
  capture: <E extends EventName>(event: E, properties: EventProperties<E>) => void;
  identify: (pseudonym: string) => void;
  reset: () => void;
}

function selectAdapter(): Analytics {
  if (import.meta.env.DEV) return noopAdapter;
  const key = env.PUBLIC_POSTHOG_KEY;
  if (!key) return noopAdapter;
  // SSR returns noop so server-side `analytics.*` calls (e.g. from load
  // functions in the typed-events phase) don't hit an uninitialized SDK.
  // The PostHog adapter is only safe to use once `init()` has run, which
  // requires `window` — that only happens on the browser.
  if (!browser) return noopAdapter;
  posthogAdapter.init(key);
  return posthogAdapter;
}

export const analytics: Analytics = selectAdapter();
