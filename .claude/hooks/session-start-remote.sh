#!/bin/bash
# Web-sandbox-only repairs run before the standard uv sync / pnpm install tail.
#
# Claude Code on the web ships a frozen container image: uv 0.8.17 whose
# Python download catalog stops at 3.14.0rc2.  Pydantic 2.12+ calls
# `typing._eval_type(..., prefer_fwd_module=True)`, which rc2 doesn't
# support, so any import chain that touches django-ninja blows up with an
# AssertionError deep inside pydantic.  The fix is to upgrade uv and
# install a real 3.14.  This only matters in the sandbox — localhost
# Claude Code sessions skip this block entirely to avoid mutating the
# user's global uv or downloading a Python they don't need.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

uv self update
uv python install 3.14
