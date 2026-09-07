#!/usr/bin/env node
// Rewrite every `components['schemas']['Name']` reference in frontend/src into
// a named import + bare-name use against `$lib/api/schema`.
//
// Idempotent: a fully-converted tree produces zero rewrites.
// Run from repo root or frontend/; resolves paths relative to the script.

import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HERE, '..', '..');
const SRC = resolve(FRONTEND, 'src');
const CLIENT_PATH = resolve(SRC, 'lib/api/client.ts');
const SCHEMA_DTS = resolve(SRC, 'lib/api/schema.d.ts');

const INDEXED_RE = /components\[(['"])schemas\1\]\[(['"])([A-Za-z_][A-Za-z0-9_]*)\2\]/g;

// Trivial alias: `type X = components['schemas']['X'];` (or the exported
// form). Same identifier on both sides — after the bare-name rewrite this
// becomes `type X = X`, which is a self-reference. Replace these up front:
// the local alias is redundant once `X` is imported by name.
const SELF_ALIAS_RE =
  /^([ \t]*)(export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*components\[(['"])schemas\4\]\[(['"])\3\5\]\s*;[ \t]*\n?/gm;

// Capture an existing `import type { ... } from '$lib/api/schema'` line.
// Tolerant of indentation (svelte script blocks indent 2 spaces) and quote
// style; specifiers are captured as a single chunk for splitting.
// Matches both the canonical `$lib/api/schema` form and the bare `./schema`
// form used inside `frontend/src/lib/api/`. The script preserves whichever
// form the file already uses (capture group 4) — switching paths is out of
// scope.
const SCHEMA_IMPORT_RE =
  /^([ \t]*)import\s+type\s+\{([^}]*)\}\s+from\s+(['"])(\$lib\/api\/schema|\.\/schema)\3;?[ \t]*$/m;

function listSourceFiles() {
  // git ls-files honors .gitignore, skips schema.d.ts (gitignored), and is
  // fast. Filter to source extensions this codemod supports.
  const out = execSync('git ls-files frontend/src', {
    cwd: resolve(FRONTEND, '..'),
    encoding: 'utf8',
  });
  return out
    .split('\n')
    .filter(Boolean)
    .map((p) => resolve(FRONTEND, '..', p))
    .filter((p) => /\.(ts|svelte)$/.test(p))
    .filter((p) => p !== CLIENT_PATH && p !== SCHEMA_DTS);
}

function parseSpecifiers(chunk) {
  return chunk
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatSpecifiers(specs) {
  return ` ${specs.join(', ')} `;
}

function rewriteFile(path) {
  const original = readFileSync(path, 'utf8');
  if (!INDEXED_RE.test(original)) return false;
  INDEXED_RE.lastIndex = 0;

  // First collapse self-named aliases (`type X = components[…]['X']`).
  // Non-exported aliases are removed entirely. Exported aliases turn into
  // `export type { X };` — the import-block update below brings `X` into
  // scope, and the bare re-export preserves the module's public surface
  // for downstream consumers.
  const names = new Set();
  const withoutSelfAliases = original.replace(SELF_ALIAS_RE, (_m, indent, exp, name) => {
    names.add(name);
    return exp ? `${indent}export type { ${name} };\n` : '';
  });

  // Then rewrite remaining `components['schemas']['X']` to bare `X`.
  const rewritten = withoutSelfAliases.replace(INDEXED_RE, (_m, _q1, _q2, name) => {
    names.add(name);
    return name;
  });

  // Update or insert the `import type { ... } from '$lib/api/schema'` line.
  let next;
  const importMatch = rewritten.match(SCHEMA_IMPORT_RE);
  if (importMatch) {
    const [line, indent, specChunk, quote, modulePath] = importMatch;
    const specs = parseSpecifiers(specChunk);
    const specSet = new Set(specs);
    for (const n of names) specSet.add(n);

    // Drop `components` if it no longer appears as an identifier in the
    // file outside this import line. Specifier-level only — `paths` (or
    // others) stay. The `[` / `.` / `,` / `>` lookahead deliberately
    // narrows to "used as a value/type identifier"; this avoids false
    // positives from string content in unrelated imports like
    // `import X from '$lib/components/Y.svelte'`, where the path contains
    // the substring `components` but isn't an identifier reference.
    const tail = rewritten.slice(importMatch.index + line.length);
    const head = rewritten.slice(0, importMatch.index);
    const restOfFile = head + tail;
    if (!/\bcomponents\s*[[.,>]/.test(restOfFile)) {
      specSet.delete('components');
    }

    const finalSpecs = [...specSet].sort();
    const replacement = `${indent}import type {${formatSpecifiers(finalSpecs)}} from ${quote}${modulePath}${quote};`;
    next = rewritten.replace(SCHEMA_IMPORT_RE, replacement);
  } else {
    // No existing import — insert one. This branch should be uncommon on the
    // current tree, but handle it for future files added without an existing
    // `components` import.
    const finalSpecs = [...names].sort();
    const importLine = `import type { ${finalSpecs.join(', ')} } from '$lib/api/schema';\n`;
    if (path.endsWith('.svelte')) {
      next = rewritten.replace(/(<script\b[^>]*>\s*)/, `$1${importLine}`);
    } else {
      next = importLine + rewritten;
    }
  }

  if (next === original) return false;
  writeFileSync(path, next, 'utf8');
  return true;
}

function main() {
  const files = listSourceFiles();
  let changed = 0;
  for (const f of files) {
    if (rewriteFile(f)) changed += 1;
  }
  console.log(`Rewrote ${changed} file(s).`);
}

main();
