#!/bin/bash
# PreToolUse hook: run formatters on staged files before git commit,
# so pre-commit hooks pass on the first try without re-staging.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only act on git commit commands
if [[ "$COMMAND" != git\ commit* ]]; then
  exit 0
fi

# --- Backend: ruff check --fix + ruff format ---
STAGED_BACKEND=$(git diff --cached --name-only -- backend/)
if [ -n "$STAGED_BACKEND" ]; then
  uv run --directory backend ruff check --fix . 2>/dev/null
  uv run --directory backend ruff format . 2>/dev/null

  echo "$STAGED_BACKEND" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

# --- Frontend: prettier --write ---
STAGED_FRONTEND=$(git diff --cached --name-only -- frontend/)
if [ -n "$STAGED_FRONTEND" ]; then
  (cd frontend && pnpm prettier --write . 2>/dev/null)

  echo "$STAGED_FRONTEND" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

# --- Markdown: prettier --write ---
STAGED_MD=$(git diff --cached --name-only -- '*.md' | grep -v '^CLAUDE\.md$' | grep -v '^AGENTS\.md$')
if [ -n "$STAGED_MD" ]; then
  echo "$STAGED_MD" | xargs npx prettier@3.8.1 --write 2>/dev/null

  echo "$STAGED_MD" | while IFS= read -r file; do
    if [ -f "$file" ]; then
      git add "$file"
    fi
  done
fi

exit 0
