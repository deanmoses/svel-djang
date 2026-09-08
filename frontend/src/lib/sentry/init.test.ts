import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock @sentry/sveltekit so the init code runs against spies instead of
// boot a real SDK. httpIntegration is exercised directly by the SSR test
// to pin the request-body suppression contract.
vi.mock('@sentry/sveltekit', () => ({
  init: vi.fn(),
  httpIntegration: vi.fn((opts) => ({ name: 'Http', options: opts })),
  handleErrorWithSentry: vi.fn(() => vi.fn()),
  sentryHandle: vi.fn(() => vi.fn()),
}));

// Default mocks for both env surfaces; each test overrides via vi.doMock.
vi.mock('$env/dynamic/private', () => ({ env: {} }));
vi.mock('$env/dynamic/public', () => ({ env: {} }));

describe('SSR Sentry init (instrumentation.server.ts)', () => {
  // instrumentation.server.ts reads DSN/release from process.env directly,
  // not from $env/dynamic — see the file's comment for why. Tests set/clear
  // process.env entries to drive each scenario.
  const ENV_KEYS = ['PUBLIC_SENTRY_DSN', 'RAILWAY_GIT_COMMIT_SHA', 'SENTRY_DSN'] as const;
  const originalEnv: Record<string, string | undefined> = {};

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    for (const key of ENV_KEYS) {
      originalEnv[key] = process.env[key];
      Reflect.deleteProperty(process.env, key);
    }
  });

  afterEach(() => {
    for (const key of ENV_KEYS) {
      if (originalEnv[key] === undefined) Reflect.deleteProperty(process.env, key);
      else process.env[key] = originalEnv[key];
    }
  });

  it('does not call Sentry.init when PUBLIC_SENTRY_DSN is unset', async () => {
    const Sentry = await import('@sentry/sveltekit');
    await import('../../instrumentation.server');
    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it('routes SSR events to the frontend DSN (PUBLIC_SENTRY_DSN), not the backend DSN', async () => {
    // Critical invariant: SSR is frontend code; its events must go to
    // flipcommons-frontend (PUBLIC_SENTRY_DSN), NOT flipcommons-backend
    // (SENTRY_DSN). Setting both with different values catches any refactor
    // that wires the wrong one.
    process.env.PUBLIC_SENTRY_DSN = 'https://frontend-project@sentry.example/2';
    process.env.SENTRY_DSN = 'https://backend-project@sentry.example/1';
    process.env.RAILWAY_GIT_COMMIT_SHA = 'abc123';

    const Sentry = await import('@sentry/sveltekit');
    await import('../../instrumentation.server');

    expect(Sentry.init).toHaveBeenCalledOnce();
    const initArgs = vi.mocked(Sentry.init).mock.calls[0][0]!;
    expect(initArgs.dsn).toBe('https://frontend-project@sentry.example/2');
    // Mirrors the option instrumentation.server.ts still passes. Sentry 10.73
    // deprecates it in favour of `dataCollection`; migrating is a change to
    // what the SDK collects, so it happens on its own, not here.
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    expect(initArgs.sendDefaultPii).toBe(false);
    expect(initArgs.tracesSampleRate).toBe(0);
    expect(initArgs.release).toBe('abc123');

    // Pins the request-body suppression contract — a refactor that drops
    // the option fails this test.
    expect(Sentry.httpIntegration).toHaveBeenCalledWith({ maxIncomingRequestBodySize: 'none' });
    expect(initArgs.integrations).toEqual([
      expect.objectContaining({ options: { maxIncomingRequestBodySize: 'none' } }),
    ]);
  });
});

describe('Browser Sentry init (hooks.client.ts)', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('does not call Sentry.init when PUBLIC_SENTRY_DSN is empty', async () => {
    vi.doMock('$env/dynamic/public', () => ({ env: {} }));
    const Sentry = await import('@sentry/sveltekit');
    await import('../../hooks.client');
    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it('calls Sentry.init when PUBLIC_SENTRY_DSN is set', async () => {
    vi.doMock('$env/dynamic/public', () => ({
      env: {
        PUBLIC_SENTRY_DSN: 'https://example@sentry.example/2',
        PUBLIC_RAILWAY_GIT_COMMIT_SHA: 'def456',
      },
    }));
    const Sentry = await import('@sentry/sveltekit');
    await import('../../hooks.client');

    expect(Sentry.init).toHaveBeenCalledOnce();
    const initArgs = vi.mocked(Sentry.init).mock.calls[0][0]!;
    expect(initArgs.dsn).toBe('https://example@sentry.example/2');
    expect(initArgs.release).toBe('def456');
    // As above: mirrors what hooks.client.ts passes.
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    expect(initArgs.sendDefaultPii).toBe(false);
    expect(initArgs.tracesSampleRate).toBe(0);
    // No replay or feedback integrations.
    expect(initArgs.integrations).toBeUndefined();
  });
});
