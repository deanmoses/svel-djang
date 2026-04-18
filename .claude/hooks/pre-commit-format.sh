#!/bin/bash
# PreToolUse hook: run formatters on staged files before git commit,
# so pre-commit hooks pass on the first try without re-staging.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only act on git commit commands
if [[ "$COMMAND" != git\ commit* ]]; then
  exit 0
fi

# Errors from formatters go to this log (visible via stderr), but the hook
# never blocks the commit — exit 0 at the end regardless.
LOG=/tmp/pre-commit-format-hook.log
: > "$LOG"

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
  uv run --directory backend ruff check --fix . >>"$LOG" 2>&1
  uv run --directory backend ruff format . >>"$LOG" 2>&1

  echo "$STAGED_BACKEND" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

# --- Frontend: prettier --write ---
STAGED_FRONTEND=$(git diff --cached --name-only -- frontend/)
if [ -n "$STAGED_FRONTEND" ]; then
  (cd frontend && pnpm prettier --write . >>"$LOG" 2>&1)

  echo "$STAGED_FRONTEND" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

# --- Markdown: prettier --write ---
STAGED_MD=$(git diff --cached --name-only -- '*.md' | grep -v '^CLAUDE\.md$' | grep -v '^AGENTS\.md$')
if [ -n "$STAGED_MD" ]; then
  echo "$STAGED_MD" | xargs npx prettier@3.8.1 --write >>"$LOG" 2>&1

  echo "$STAGED_MD" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
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
