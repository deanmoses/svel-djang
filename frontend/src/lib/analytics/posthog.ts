// PostHog adapter — the only file outside `analytics/` allowed to import
// `posthog-js`. Module scope is intentionally side-effect-free: nothing here
// touches `window` or fires a request at import time. `index.ts` is the only
// caller of `init()` and only calls it when `browser` is true and a real key
// is present.

import posthog from 'posthog-js';

import { config } from './config';
import type { Analytics } from './index';

export interface PosthogAdapter extends Analytics {
  init: (key: string) => void;
}

export const posthogAdapter: PosthogAdapter = {
  init(key) {
    posthog.init(key, config);
  },
  // `capture_pageview: 'history_change'` in the init config fires `$pageview`
  // on initial load and every CSR navigation automatically, so this method is
  // a no-op. The method exists for symmetry with the backend interface and
  // future-proofing if we switch providers.
  pageview() {},
  // No typed events are emitted yet (registry is empty). Once the typed-events
  // frontend plan lands, these forward to posthog.capture / .identify / .reset.
  capture() {},
  identify() {},
  reset() {},
};
