#!/bin/bash
# PreToolUse hook: auto-approve Bash commands that match allowed prefixes,
# bypassing Claude Code's broken quote-tracking in prefix matching.
#
# This fixes a known bug where single quotes in commands cause
# permission prompts even when the command prefix is explicitly allowed.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Allowed command prefixes — add more as needed
ALLOWED_PREFIXES=(
  "curl"
  "detect-secrets scan"
  "duckdb"
  "find"
  "gh "
  "git add"
  "git branch"
  "git cherry-pick"
  "git checkout"
  "git count-objects"
  "git diff"
  "git fetch"
  "git log"
  "git ls-remote"
  "git merge"
  "git mv"
  "git pull"
  "git push"
  "git rebase"
  "git remote"
  "git rev-list"
  "git rev-parse"
  "git rm"
  "git show"
  "git stash"
  "git status"
  "git switch"
  "git tag"
  "grep"
  "ls"
  "make"
  "npm view"
  "npx eslint"
  "npx prettier"
  "npx vitest"
  "pnpm"
  "pre-commit"
  "python3"
  "pyenv versions"
  "uv add"
  "uv pip list"
  "uv run"
  "uv sync"
  "uv tool run"
  "wc"
)

for prefix in "${ALLOWED_PREFIXES[@]}"; do
  if [[ "$COMMAND" == "$prefix"* ]]; then
    echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}'
    exit 0
  fi
done

# Not matched — fall through to normal permission handling
exit 0
