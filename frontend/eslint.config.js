import js from '@eslint/js';
import vitest from '@vitest/eslint-plugin';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';

// Named `no-restricted-imports` entries, shared by the scoped blocks below.
// Flat config does not union this rule across overrides (the last matching block
// wins), so each block lists the entries it needs by name; defining each message
// once here keeps them consistent. The component-architecture boundaries
// (NO_PAGES / NO_SITE / NO_ROUTES) are documented in
// docs/plans/SvelteComponentReorg.md.

// posthog-js is the analytics vendor SDK. Only src/lib/analytics/posthog.ts may
// touch it; everywhere else goes through the $lib/analytics abstraction, keeping
// the vendor boundary one file wide so a future swap is mechanical.
const NO_POSTHOG = {
  name: 'posthog-js',
  message:
    "Don't import posthog-js directly — use the `analytics` export from $lib/analytics. Only src/lib/analytics/posthog.ts may touch the SDK.",
  allowTypeImports: true,
};
// The createApiClient factory is an api/ implementation detail. App code uses the
// default `client` ($lib/api/client) or createServerClient ($lib/api/server);
// reaching into $lib/api/internal/ from outside api/ is a layering bug.
const NO_API_INTERNAL = {
  group: ['$lib/api/internal/*', '**/api/internal/*'],
  message:
    "Don't import from $lib/api/internal/ — use the default `client` from $lib/api/client or `createServerClient` from $lib/api/server.",
};
// pages/ shells are page bodies — importable only from routes/ and from within
// pages/. Importing a page shell from a general component is a layering mistake.
const NO_PAGES = {
  group: ['$lib/components/pages/**'],
  message: 'pages/ shells are page bodies — import them only from routes/ or from within pages/.',
};
// layout/site/ holds the site-chrome shells (SiteShell etc.), wired into the app
// only by the root layout, so only routes/ may import them. The page-level layer
// components compose with is layout/page/ (Page, MetaTags, JsonLd, …) — not site/.
const NO_SITE = {
  group: ['$lib/components/layout/site/**'],
  message:
    'layout/site/ holds site-chrome shells — import them only from routes/ (they are wired in by the root layout). Page-level primitives live in layout/page/.',
};
// $lib must not depend on routes/: shared code belongs in $lib, single-route code
// stays route-private (routes/.../_components/). This is the boundary the
// route-private / switch-promotion conventions rely on. Relative specifiers are
// used because routes aren't $lib-addressable; test files are exempt (route-loader
// tests legitimately import `+layout.server`).
const NO_ROUTES = {
  group: ['**/routes/**'],
  message:
    '$lib must not import from routes/ — promote shared code into $lib, or keep single-route code route-private under routes/.../_components/. (Tests may import route loaders.)',
};
// ui/ is primitives-only and domain-free: it may compose other ui/ primitives
// but must not import any non-ui component. Dependency flows outward only. The
// `!…/ui` dir line is required alongside `!…/ui/**`: gitignore semantics can't
// re-include children while the parent dir stays excluded.
const NO_NON_UI = {
  group: ['$lib/components/**', '!$lib/components/ui', '!$lib/components/ui/**'],
  message: 'ui/ is primitives-only — it may not import from any sibling components folder.',
};
// Files that get type-aware linting; see the typed block near the bottom.
const TYPED_FILES = ['src/**/*.ts'];
// Test code exercised by the production-only typed rules below.
const TYPED_TEST_FILES = [
  'src/**/*.test.ts',
  'src/**/*.spec.ts',
  'src/tests/**',
  'src/**/*.fixture.ts',
];
const SRC_FILES = [
  'src/**/*.ts',
  'src/**/*.js',
  'src/**/*.svelte',
  'src/**/*.svelte.ts',
  'src/**/*.svelte.js',
];

export default ts.config(
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs.recommended,
  prettier,
  ...svelte.configs.prettier,
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  {
    files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
    languageOptions: {
      parserOptions: {
        parser: ts.parser,
      },
    },
  },
  {
    rules: {
      'svelte/no-navigation-without-resolve': 'off',
      eqeqeq: ['error', 'always', { null: 'ignore' }],
      // Sequential awaits in a loop are usually an unintended serialization of
      // work that Promise.all would run concurrently.
      'no-await-in-loop': 'error',
      // Method shorthand (`f(x): void`) is checked bivariantly, so
      // `strictFunctionTypes` does not apply to it; the property form
      // (`f: (x) => void`) gets the sound contravariant check.
      '@typescript-eslint/method-signature-style': 'error',
      // An inline `import { type A, b }` where every specifier is a type still
      // emits a bare side-effect import. The top-level `import type` form
      // erases cleanly, which is what `verbatimModuleSyntax` assumes.
      '@typescript-eslint/no-import-type-side-effects': 'error',
      // Every component's <script> is TypeScript; a block that omits the
      // attribute silently opts out of type checking.
      'svelte/block-lang': ['error', { enforceScriptPresent: false, script: 'ts' }],
      'svelte/no-bind-value-on-checkable-inputs': 'error',
      // `Foo.svelte` alongside a `Foo.svelte.ts` runes module: the two resolve
      // through different import specifiers and reading one as the other is a
      // silent import mistake.
      'svelte/no-conflicting-module-names': 'error',
      // `<slot name={x}>` is a legacy-slot construct with no runes equivalent.
      'svelte/no-dynamic-slot-name': 'error',
      // `{{ expr }}` is a single mustache wrapping a parenthesized expression,
      // not interpolation — the extra braces render as literal braces.
      'svelte/no-extra-reactive-curlies': 'error',
      'svelte/no-nested-style-tag': 'error',
      // The runes-aware counterpart to core `prefer-const`, which does not see
      // into a component's <script>. A `$state` object that is only ever
      // mutated wants `const` — the proxy carries the mutations. `$props` and
      // `$derived` are exempt by default, being the two that can need `let`.
      'svelte/prefer-const': 'error',
      // `$derived.by()` is for multi-statement bodies; a callback that is one
      // return statement reads as `$derived()`.
      'svelte/prefer-derived-over-derived-by': 'error',
      'svelte/require-event-prefix': 'error',
      // A `style` attribute carrying a mustache is re-parsed on every update;
      // the `style:` directive patches the one property that changed.
      'svelte/require-optimized-style-attribute': 'error',
      'svelte/valid-style-parse': 'error',
      //
      // Store rules. The app is runes-only, so these report nothing today —
      // they exist to keep it that way, catching a legacy store pattern the
      // first time one is written rather than after it has spread.
      //
      'svelte/derived-has-same-inputs-outputs': 'error',
      'svelte/no-ignored-unsubscribe': 'error',
      'svelte/prefer-destructured-store-props': 'error',
      'svelte/require-store-callbacks-use-set-param': 'error',
      'svelte/require-stores-init': 'error',
      // Standard convention: `_`-prefixed args/vars are intentionally unused.
      // Lets snippets accept required arguments they don't need to reference.
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
      // Use named imports from `$lib/api/schema` instead of indexed access.
      // `openapi-typescript --root-types` emits top-level aliases for every
      // component schema, so `components['schemas']['Foo']` is always
      // expressible as `Foo`. Indexed access is allowed only in
      // `src/lib/api/client.ts` (the override below).
      // Type-position `components['schemas'][...]` parses as a
      // TSIndexedAccessType, not a MemberExpression — that's why this rule
      // targets the TS-specific node.
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "TSIndexedAccessType[objectType.typeName.name='components'][indexType.literal.value='schemas']",
          message:
            "Use a named import from '$lib/api/schema' instead of components['schemas'][...].",
        },
        // Node writes console.warn to stderr alongside console.error, and
        // Railway classifies a plain-text stderr line as an error — so an SSR
        // console.warn is indistinguishable from a fault in the log explorer.
        // $lib/log emits JSON carrying its own level, which Railway reads
        // instead. Browser-only code gains nothing from the rule but loses
        // nothing either: the logger falls back to console off the server.
        {
          selector: "MemberExpression[object.name='console']",
          message:
            'Use `getLogger()` from $lib/log instead of console.* — a plain SSR console line is classified by its stream, so warnings read as errors in Railway.',
        },
      ],
    },
  },
  //
  // `no-restricted-imports` blocks below. Flat config does NOT union this rule
  // across overrides — the LAST matching block wins and silently drops earlier
  // options — so every block restates the full set it needs. Ordered so the
  // last block matching a file is its effective rule set:
  //
  //   1. base (all src) — vendor boundaries + no reaching into page/site shells
  //   2. routes/        — exempt from the shell rules (routes compose them)
  //   3. lib/           — adds the $lib → routes/ boundary
  //   4. pages/         — page shells may cross-import each other
  //   5. ui/            — primitives-only (subsumes the shell rules)
  //   6. api/           — may import its own internals
  //   7. posthog.ts     — the one file allowed the analytics SDK
  //   8. tests          — vendor boundaries only (the structural rules guard the
  //                       production graph; tests import across folders for setup)
  //
  {
    // Base for all src: vendor boundaries + no reaching into the page/site
    // shells. routes/ relaxes the shell rules below (it wires shells in).
    files: SRC_FILES,
    rules: {
      'no-restricted-imports': [
        'error',
        { paths: [NO_POSTHOG], patterns: [NO_API_INTERNAL, NO_SITE, NO_PAGES] },
      ],
    },
  },
  {
    // routes/ may import page shells and site shells — that's what routes are
    // for. Vendor boundaries still apply.
    files: ['src/routes/**'],
    rules: {
      'no-restricted-imports': ['error', { paths: [NO_POSTHOG], patterns: [NO_API_INTERNAL] }],
    },
  },
  {
    // lib/ adds the $lib → routes/ boundary on top of the base set.
    files: ['src/lib/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        { paths: [NO_POSTHOG], patterns: [NO_API_INTERNAL, NO_SITE, NO_PAGES, NO_ROUTES] },
      ],
    },
  },
  {
    // pages/ shells import each other (across record/listing/error subfolders),
    // so drop NO_PAGES — but they must not import site shells or routes/.
    files: ['src/lib/components/pages/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        { paths: [NO_POSTHOG], patterns: [NO_API_INTERNAL, NO_SITE, NO_ROUTES] },
      ],
    },
  },
  {
    // ui/ is primitives-only and domain-free: it may compose other ui/
    // primitives but no other component (NO_NON_UI subsumes the page/site
    // rules). Dependency flows outward only.
    files: ['src/lib/components/ui/**'],
    rules: {
      'no-restricted-imports': [
        'error',
        { paths: [NO_POSTHOG], patterns: [NO_API_INTERNAL, NO_NON_UI, NO_ROUTES] },
      ],
    },
  },
  {
    // api/ may import its own internals (drops NO_API_INTERNAL); still $lib, so
    // the routes/ boundary holds.
    files: ['src/lib/api/**'],
    rules: {
      'no-restricted-imports': ['error', { paths: [NO_POSTHOG], patterns: [NO_ROUTES] }],
    },
  },
  {
    // The PostHog adapter is the one file allowed to touch the SDK (drops
    // NO_POSTHOG); the api-internal and routes/ boundaries still hold.
    files: ['src/lib/analytics/posthog.ts'],
    rules: {
      'no-restricted-imports': ['error', { patterns: [NO_API_INTERNAL, NO_ROUTES] }],
    },
  },
  {
    // Test files: vendor boundaries only. The structural component boundaries
    // above guard the production dependency graph; tests don't ship and
    // legitimately import across folders for setup (route loaders, page shells,
    // fixtures). Last so it overrides the folder blocks for any test under them.
    files: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
    rules: {
      'no-restricted-imports': ['error', { paths: [NO_POSTHOG], patterns: [NO_API_INTERNAL] }],
    },
  },
  {
    // The page injects the @scalar/api-reference bundle from jsdelivr at
    // runtime and calls the `Scalar` global it defines.
    files: ['src/routes/api-docs/+page.svelte'],
    languageOptions: {
      globals: { Scalar: 'readonly' },
    },
  },
  {
    files: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
    ...vitest.configs.recommended,
    rules: {
      ...vitest.configs.recommended.rules,
      'vitest/no-disabled-tests': 'error',
      // An `expect` reachable only through a branch is an assertion the suite
      // may never run: the test then passes having verified nothing. Narrow a
      // union with `assert(x.kind === 'y')`, which fails the test outright.
      'vitest/no-conditional-expect': 'error',
      // A test whose body never asserts passes by reaching the end.
      'vitest/expect-expect': 'error',
      // Off pending cleanup — real hits in the current suite.
      'vitest/prefer-called-exactly-once-with': 'off',
      // Vitest's `expect(value, message)` takes a second argument that Jest's
      // does not, and the convention tests use it to say how to fix a
      // violation. maxArgs:2 keeps the arity check without banning that.
      'vitest/valid-expect': ['error', { maxArgs: 2 }],
      // `describe(key)` over a codegen'd key list is how the convention tests
      // fan out per entity. Only describe names are exempt — an `it` title
      // still has to be a literal, so a test can't hide behind a variable.
      'vitest/valid-title': ['error', { ignoreTypeOfDescribeName: true }],
    },
  },
  //
  // Type-aware rules. Scoped to src TypeScript: pulling type information into
  // `.svelte` takes lint from ~14s to ~85s, and svelte-eslint-parser types
  // snippet and callback-prop parameters as `any` where the compiler types them
  // properly, so the unsafe-* family reports over a thousand phantom findings
  // there.
  //
  ...ts.configs.strictTypeChecked.map((c) => ({ ...c, files: TYPED_FILES })),
  {
    files: TYPED_FILES,
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // strictTypeChecked resets this to bare `error`, dropping the `^_`
      // convention configured above.
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
      // A union member added to a codegen'd type — an EntityKey from
      // export_entity_meta, a schema `reason` literal — has to break every
      // switch that needs a new arm, or the frontend silently drops the case.
      // A `default` arm counts as exhaustive, so switches that legitimately
      // want a catch-all are unaffected.
      '@typescript-eslint/switch-exhaustiveness-check': [
        'error',
        { considerDefaultExhaustiveForUnions: true, allowDefaultCaseForExhaustiveSwitch: true },
      ],
      // The write side of `no-import-type-side-effects`: that rule fixes the
      // inline `{ type A }` form, this one keeps a type from being imported as
      // a value in the first place. `disallowTypeAnnotations: false` leaves
      // inline `import('./x').Y` alone — tests use it to type vi.mock factories.
      '@typescript-eslint/consistent-type-imports': [
        'error',
        {
          prefer: 'type-imports',
          fixStyle: 'separate-type-imports',
          disallowTypeAnnotations: false,
        },
      ],
      '@typescript-eslint/consistent-type-exports': 'error',
      // `.sort()` with no comparator sorts by string codepoint, so [1, 10, 2]
      // is the sorted order for numbers. String arrays are exempt: codepoint
      // order is what they want, and `localeCompare` would be wrong for slugs.
      '@typescript-eslint/require-array-sort-compare': ['error', { ignoreStringArrays: true }],
      // `.filter(p)[0]` walks the whole array and allocates; `.find(p)` stops.
      '@typescript-eslint/prefer-find': 'error',
      // A parameter after a defaulted one can never be omitted, so the default
      // is unreachable and every caller must pass `undefined` positionally.
      '@typescript-eslint/default-param-last': 'error',
      '@typescript-eslint/no-useless-empty-export': 'error',
      // `||` falls back on every falsy value, so a legitimate 0 or false is
      // silently replaced by the default. `??` only covers null/undefined.
      //
      // Strings are exempt because the codebase uses `||` on them deliberately:
      // `env.SITE_ORIGIN?.trim() || url.origin` has to treat an unset variable
      // and a blank one alike, and `??` there would accept '' as the origin.
      // Ternaries are exempt for the same reason — `x ? x : ''` is written when
      // the empty case is the point.
      '@typescript-eslint/prefer-nullish-coalescing': [
        'error',
        { ignorePrimitives: { string: true }, ignoreTernaryTests: true },
      ],
      // Private fields never reassigned outside the constructor.
      '@typescript-eslint/prefer-readonly': 'error',
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }],
      '@typescript-eslint/no-confusing-void-expression': [
        'error',
        {
          ignoreArrowShorthand: true,
          ignoreVoidOperator: true,
          ignoreVoidReturningFunctions: true,
        },
      ],
      // SvelteKit declares error() and redirect() as returning `never`, so
      // every `throw error(...)` trips this and no configuration satisfies it.
      '@typescript-eslint/only-throw-error': 'off',
      // Reading a method off its object drops `this`. In tests this mostly
      // means asserting on a global rather than on the spy that replaced it —
      // `expect(confirmSpy)`, not `expect(window.confirm)`.
      '@typescript-eslint/unbound-method': 'error',
      // Off pending cleanup.
      '@typescript-eslint/no-floating-promises': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      '@typescript-eslint/no-unnecessary-condition': 'off',
      '@typescript-eslint/no-unnecessary-type-assertion': 'off',
      '@typescript-eslint/no-unsafe-argument': 'off',
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
      '@typescript-eslint/no-unsafe-return': 'off',
      '@typescript-eslint/require-await': 'off',
    },
  },
  {
    // Rules whose findings are almost entirely stub casts when pointed at
    // tests — `as unknown as Parameters<typeof load>[0]` and the like, which
    // are deliberate. Production code is where they earn their keep.
    files: TYPED_FILES,
    ignores: TYPED_TEST_FILES,
    rules: {
      '@typescript-eslint/no-non-null-assertion': 'error',
      '@typescript-eslint/no-unsafe-argument': 'error',
      '@typescript-eslint/no-unsafe-return': 'error',
      '@typescript-eslint/require-await': 'error',
      '@typescript-eslint/no-unsafe-assignment': 'error',
      '@typescript-eslint/no-unsafe-member-access': 'error',
      '@typescript-eslint/no-unnecessary-type-assertion': 'error',
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-unsafe-call': 'error',
    },
  },
  {
    // One-off codemod scripts are CLI tools, not app code: they run under plain
    // node with a terminal attached, never on the SSR request path, so console
    // is their correct output channel and $lib is not importable from them.
    // (Dropping the whole rule also drops the schema selector, which is a
    // TS-only concern these .mjs files can't express anyway.)
    files: ['scripts/**'],
    rules: {
      'no-restricted-syntax': 'off',
    },
  },
  {
    ignores: ['build/', '.svelte-kit/', 'dist/', 'src/lib/api/schema.d.ts'],
  },
);
