# Analytics

We use **[PostHog](https://posthog.com)** for product analytics.

## Current surface area

Pageviews only. No typed events.

### Enabling & disabling analytics

Analytics can only be enabled in prod. Disabling analytics in prod means clearing `PUBLIC_POSTHOG_KEY` and redeploying — same pattern as `PUBLIC_SENTRY_DSN`.

`posthog-js` ships in every production bundle once any call site imports `$lib/analytics`, regardless of whether the key is set. The runtime guard is the master switch, not the bundle.

## Privacy posture (what's stored)

PostHog **does not store**: IPs, cookies, localStorage identity, autocaptured clicks/inputs, screen/viewport dimensions, device model, UTM/click-id campaign params, search-engine keyword props, URL query strings.

PostHog **does store**: path-only pageviews, browser/OS user-agent fields it derives server-side, referrer origin+path (no query), session id (memory-scoped, dies on tab close).

### Where each guarantee is enforced

Every item in the not-stored list is enforced by `frontend/src/lib/analytics/config.ts` and asserted by `config.test.ts` — except IPs.

**IP discard lives outside this repo.** The browser SDK cannot suppress `$ip`: PostHog fills it in from the request whenever the client doesn't supply one, and a browser has no way to know its own public IP. The only control is the **Discard client IP data** toggle in the PostHog project settings (Settings → Data capture). Nothing in the codebase can check it, so if that toggle is turned off — or the analytics project is recreated without it — the IP claim above and the matching sentence on the public privacy page silently become false.

For the project-wide privacy contract see [Privacy.md](Privacy.md).
