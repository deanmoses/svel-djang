# Backend Improvements

Audit of the Django backend at [backend/](../../backend/) against modern Python/Django best practices. Goal: move from "well-engineered" to "glowing exemplar."

## High-impact gaps

### Static type checking gaps

We just added type checking and grandfathered in a lot of errors. The exception baseline is at backend/.basedpyright/baseline.json. It's a single JSON file keyed by file path, with each entry storing the rule name, code range, and a hash — basedpyright matches by position+hash so edits to a line generally invalidate the baseline entry (forcing a re-check). To retire baseline entries after fixing them: cd backend && uv run basedpyright --writebaseline.

### No test coverage or parallelization

[backend/pytest.ini](../../backend/pytest.ini) has no `pytest-cov`, `pytest-xdist`, or `pytest-timeout`. For a project where tests gate commits via pre-commit, `-n auto` alone would noticeably speed up the hook. Add coverage thresholds in `pyproject.toml`.

## Mid-impact

- **Dependency groups**: [backend/pyproject.toml](../../backend/pyproject.toml) has only a `dev` group — split into `test`, `lint`, `dev` for leaner CI installs.
- **Gunicorn config**: [scripts/start-production](../../scripts/start-production) hardcodes `--workers 2`. Drive from env, add `--timeout`, `--graceful-timeout`, `--max-requests` for memory hygiene.
- **`SESSION_SAVE_EVERY_REQUEST = True`** in settings.py writes sessions on every request — fine now, expensive later.
- **No `django-axes`** or auth-endpoint rate limiting. The custom `provenance.rate_limits` covers API mutations but not login/password endpoints.
- **No CSP middleware** (`django-csp`). Caddy handles TLS/HSTS, but CSP belongs in the app.
- **Migration squashing**: no documented strategy. Large initial migrations may slow new dev setups over time.

## Minor

- No `GeneratedField` usage — `@property` patterns adequate for current schema; revisit if DB-computed fields become useful.
- No `model_bakery`/`factory-boy` — direct model creation + `bulk_create` in tests is pragmatic at current size.
- No API versioning in [backend/config/api.py](../../backend/config/api.py) — fine while schema is stable; plan an approach before the first breaking change.

## Already solid — do not regress

- **Ruff configuration** ([backend/pyproject.toml:30-92](../../backend/pyproject.toml#L30-L92)): comprehensive rule sets, well-justified per-file ignores.
- **Pre-commit hooks** ([.pre-commit-config.yaml](../../.pre-commit-config.yaml)): detect-secrets, local ruff via uv, backend/frontend test gates.
- **Django Ninja API**: auto-discovery pattern, structured error handling for validation and rate limiting, good pagination.
- **Constraint-drift meta-tests**: `test_constraint_drift.py` ensures validators stay aligned with DB constants — genuinely impressive.
- **DB pooling**: `conn_max_age=600` + `conn_health_checks=True` is the correct modern setup.
- **Claims/provenance architecture**: custom managers with atomic operations, DB-enforced invariants (e.g. `provenance_changeset_action_iff_user`).
- **CI**: `dorny/paths-filter` for selective jobs, `uv sync --frozen`, API type-generation verification.
- **Admin quality**: readonly fields, `list_select_related`, user tracking on citation admin.
- **Constraint naming helpers** in [backend/apps/core/models.py:50-68](../../backend/apps/core/models.py#L50-L68): `field_not_blank`, `nullable_id_not_empty` — reusable and auto-namespaced.

## Suggested order

1. **Type checker** (~1hr) — basedpyright or ty, strict mode on one app, expand incrementally.
2. **pytest-cov + pytest-xdist + pytest-timeout** (~30min).
3. **pydantic-settings refactor** (~1.5hr) — kills a whole class of deploy bugs.
4. **Sentry + structlog + request-ID middleware** (~2hr).
5. **pip-audit CI job + Dependabot** (~30min).

## Caveats

This audit was produced by an exploration agent reading the repo; findings should be verified before acting. In particular, confirm that no type-checking setup exists in a location the audit missed before adding one.
