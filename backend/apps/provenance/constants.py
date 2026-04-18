"""Provenance constants.

Rate-limit values govern how often a single user may create, edit, or delete
catalog records. All windows are rolling (not calendar-aligned), per-user,
and applied to user-driven ChangeSets only. Ingest is not rate-limited.
Staff accounts are exempt (enforced in :mod:`apps.provenance.rate_limits`).

See :doc:`docs/plans/RecordCreateDelete.md` for the product-level policy.
Change these values here — they are the single source of truth.
"""

REVERT_OTHERS_MIN_EDITS = 5

# Rate limits (rolling window, per user).
CREATE_RATE_LIMIT = 5
CREATE_WINDOW_SECONDS = 3600  # 1 hour

EDIT_RATE_LIMIT = 60
EDIT_WINDOW_SECONDS = 3600  # 1 hour

DELETE_RATE_LIMIT = 5
DELETE_WINDOW_SECONDS = 86400  # 1 day
