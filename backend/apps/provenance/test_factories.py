"""Test-only factories for provenance models.

Kept outside ``tests/`` so test helpers can be imported across apps
without circular dependencies or duplicated conftest fixtures.

Use these in tests instead of calling ``ChangeSet.objects.create`` directly.
They encode invariants the DB enforces (user XOR ingest_run; action iff
user) so mistakes fail at call time rather than at constraint time.
"""

from __future__ import annotations

from typing import Any

from .models import ChangeSet, ChangeSetAction, IngestRun


def user_changeset(
    user: Any,
    *,
    action: ChangeSetAction | str = ChangeSetAction.EDIT,
    note: str = "",
) -> ChangeSet:
    """Create a user-attributed ChangeSet for tests.

    Defaults to ``action=EDIT`` since that's what every pre-create test
    fixture was implicitly asserting. Callers testing create/delete/revert
    paths pass the matching action explicitly.
    """
    return ChangeSet.objects.create(user=user, action=action, note=note)


def ingest_changeset(ingest_run: IngestRun, *, note: str = "") -> ChangeSet:
    """Create an ingest-attributed ChangeSet for tests.

    Ingest ChangeSets never carry an action — that column is reserved for
    user-driven changes (see ``ChangeSet`` check constraints).
    """
    return ChangeSet.objects.create(ingest_run=ingest_run, note=note)
