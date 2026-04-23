#!/bin/bash
# Backend SessionStart chain — sandbox Python repair + venv build + migrations.
#
# Claude Code's hook runtime executes the entries in a SessionStart matcher
# **in parallel** (see https://code.claude.com/docs/en/hooks.md), so steps
# that depend on each other must live inside one script.  Without this
# bundling, ``uv sync`` races the sandbox Python repair: the sandbox ships
# uv 0.8.17 whose download catalog tops out at 3.14.0rc2, and pydantic
# 2.12 calls ``typing._eval_type(..., prefer_fwd_module=True)`` — a kwarg
# rc2 doesn't accept — so any import that touches django-ninja blows up
# with an ``AssertionError``.  Bundling the upgrade + install + sync into
# this one script guarantees the venv is built against a real 3.14.
#
# Localhost Claude Code sessions skip the ``uv self update`` + Python
# install — those mutate global tooling we don't own.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  uv self update
  uv python install 3.14
fi

( cd backend && uv sync )
( cd backend && uv run python manage.py migrate --no-input ) || true
