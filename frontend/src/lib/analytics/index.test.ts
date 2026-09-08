import { afterEach, describe, expect, it, vi } from 'vitest';

// Adapter-selection tests for the analytics module.
//
// `PUBLIC_POSTHOG_KEY` comes from `$env/dynamic/public`, so per-case the
// module's `env` export must be mocked with `vi.doMock(...)` followed by
// `vi.resetModules()` before re-importing `./index`. `vi.stubEnv` handles
// `import.meta.env.DEV`.

type IndexModule = typeof import('./index');
type NoopModule = typeof import('./noop');
type PosthogModule = typeof import('./posthog');

async function loadIndex(opts: {
  dev: boolean;
  key: string | undefined;
  browser: boolean;
}): Promise<{
  index: IndexModule;
  noop: NoopModule;
  posthog: PosthogModule;
  posthogInitMock: ReturnType<typeof vi.fn>;
}> {
  vi.resetModules();
  vi.stubEnv('DEV', opts.dev);
  vi.stubEnv('PROD', !opts.dev);

  vi.doMock('$env/dynamic/public', () => ({
    env: { PUBLIC_POSTHOG_KEY: opts.key },
  }));
  vi.doMock('$app/environment', () => ({ browser: opts.browser }));

  const posthogInitMock = vi.fn();
  vi.doMock('posthog-js', () => ({
    default: { init: posthogInitMock },
  }));

  const noop = await import('./noop');
  const posthog = await import('./posthog');
  const index = await import('./index');
  return { index, noop, posthog, posthogInitMock };
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.doUnmock('$env/dynamic/public');
  vi.doUnmock('$app/environment');
  vi.doUnmock('posthog-js');
  vi.resetModules();
});

describe('analytics adapter selection', () => {
  it('selects the noop adapter in DEV builds (key set)', async () => {
    const { index, noop, posthogInitMock } = await loadIndex({
      dev: true,
      key: 'phc_real_key',
      browser: true,
    });
    expect(index.analytics).toBe(noop.noopAdapter);
    expect(posthogInitMock).not.toHaveBeenCalled();
  });

  it('selects the noop adapter when PUBLIC_POSTHOG_KEY is blank', async () => {
    const { index, noop, posthogInitMock } = await loadIndex({
      dev: false,
      key: '',
      browser: true,
    });
    expect(index.analytics).toBe(noop.noopAdapter);
    expect(posthogInitMock).not.toHaveBeenCalled();
  });

  it('selects the noop adapter when PUBLIC_POSTHOG_KEY is undefined', async () => {
    const { index, noop, posthogInitMock } = await loadIndex({
      dev: false,
      key: undefined,
      browser: true,
    });
    expect(index.analytics).toBe(noop.noopAdapter);
    expect(posthogInitMock).not.toHaveBeenCalled();
  });

  it('selects the PostHog adapter and calls init() once on the browser when DEV=false and key is set', async () => {
    const { index, posthog, posthogInitMock } = await loadIndex({
      dev: false,
      key: 'phc_real_key',
      browser: true,
    });
    expect(index.analytics).toBe(posthog.posthogAdapter);

    const { config } = await import('./config');
    expect(posthogInitMock).toHaveBeenCalledExactlyOnceWith('phc_real_key', config);
  });
});

describe('analytics SSR guard', () => {
  it('returns the noop adapter and does not call posthog.init() under SSR (browser=false), even with a real key', async () => {
    const { index, noop, posthogInitMock } = await loadIndex({
      dev: false,
      key: 'phc_real_key',
      browser: false,
    });
    // Important: returning noop on SSR keeps server-side `analytics.*` calls
    // from hitting an uninitialized SDK once typed-events adds real call sites.
    expect(index.analytics).toBe(noop.noopAdapter);
    expect(posthogInitMock).not.toHaveBeenCalled();
  });
});
