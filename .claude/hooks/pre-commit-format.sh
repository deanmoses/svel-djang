#!/bin/bash
# PreToolUse hook: run formatters on staged files before git commit,
# so pre-commit hooks pass on the first try without re-staging.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Match `git commit` at command start or after a shell separator (&&, ||, ;, |, `(`, newline).
# Excludes plumbing like `git commit-tree` via the trailing space/end-of-string.
# This catches chained forms like `cd backend && git commit ...` that the old
# startswith check missed.
if ! printf '%s' "$COMMAND" | grep -qE '(^|[;&|(]|&&|\|\||[[:space:]])git commit([[:space:]]|$)'; then
  exit 0
fi

# Errors from formatters go to this log (visible via stderr), but the hook
# never blocks the commit — exit 0 at the end regardless.
LOG=/tmp/pre-commit-format-hook.log
: > "$LOG"

# Summary line emitted to stderr at exit so the user can see which branches
# of the hook ran (and whether any formatter failed) without digging in the log.
SUMMARY=""
note() { SUMMARY="${SUMMARY}${SUMMARY:+, }$1"; }
warn() { SUMMARY="${SUMMARY}${SUMMARY:+, }$1"; }
emit_summary() {
  if [ -n "$SUMMARY" ]; then
    echo "[pre-commit-format] $SUMMARY" >&2
  fi
}
trap emit_summary EXIT

# Always operate from repo root so `-- backend/` / `-- frontend/` path
# filters work regardless of the cwd Claude Code invoked `git commit` from.
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
  exit 0
fi
cd "$REPO_ROOT" || exit 0

# --- Backend: ruff check --fix + ruff format ---
STAGED_BACKEND=$(git diff --cached --name-only -- backend/)
if [ -n "$STAGED_BACKEND" ]; then
  rc=0
  uv run --directory backend ruff check --fix . >>"$LOG" 2>&1 || rc=$?
  uv run --directory backend ruff format . >>"$LOG" 2>&1 || rc=$?
  if [ "$rc" -eq 0 ]; then
    note "ruff ok"
  else
    warn "ruff failed (rc=$rc; see $LOG)"
  fi

  echo "$STAGED_BACKEND" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

# --- Frontend: prettier --write ---
STAGED_FRONTEND=$(git diff --cached --name-only -- frontend/)
if [ -n "$STAGED_FRONTEND" ]; then
  rc=0
  (cd frontend && pnpm prettier --write . >>"$LOG" 2>&1) || rc=$?
  if [ "$rc" -eq 0 ]; then
    note "prettier(frontend) ok"
  else
    warn "prettier(frontend) failed (rc=$rc; see $LOG)"
  fi

  echo "$STAGED_FRONTEND" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

# --- Markdown: prettier --write ---
# Filter to ACM (added/copied/modified) so staged deletions don't trip prettier.
STAGED_MD=$(git diff --cached --name-only --diff-filter=ACM -- '*.md' | grep -v '^CLAUDE\.md$' | grep -v '^AGENTS\.md$')
if [ -n "$STAGED_MD" ]; then
  rc=0
  echo "$STAGED_MD" | xargs npx prettier@3.8.1 --write >>"$LOG" 2>&1 || rc=$?
  if [ "$rc" -eq 0 ]; then
    note "prettier(md) ok"
  else
    warn "prettier(md) failed (rc=$rc; see $LOG)"
  fi

  echo "$STAGED_MD" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

if [ -z "$SUMMARY" ]; then
  note "no staged files matched"
fi

# --- Generic whitespace fixers (mirrors pre-commit-hooks built-ins) ---
# trailing-whitespace + end-of-file-fixer exclude .md; mixed-line-ending applies to all.
STAGED_ALL=$(git diff --cached --name-only --diff-filter=ACM)
if [ -n "$STAGED_ALL" ]; then
  echo "$STAGED_ALL" | while IFS= read -r file; do
    [ -f "$file" ] || continue
    # Skip binary files
    if ! grep -Iq . "$file" 2>/dev/null; then
      continue
    fi

    changed=0

    # CRLF -> LF (all files)
    if grep -q $'\r' "$file" 2>/dev/null; then
      LC_ALL=C sed -i '' $'s/\r$//' "$file"
      changed=1
    fi

    # trailing-whitespace + end-of-file-fixer skip .md
    case "$file" in
      *.md) ;;
      *)
        # Strip trailing whitespace on each line
        if grep -qE '[ 	]+$' "$file" 2>/dev/null; then
          LC_ALL=C sed -i '' -E 's/[[:space:]]+$//' "$file"
          changed=1
        fi
        # Ensure file ends with exactly one newline
        if [ -s "$file" ] && [ "$(tail -c 1 "$file" | xxd -p)" != "0a" ]; then
          printf '\n' >> "$file"
          changed=1
        fi
        ;;
    esac

    if [ "$changed" = "1" ]; then
      git add "$file"
    fi
  done
fi

exit 0
