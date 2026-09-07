"""Meta-test: per-row ``capabilities`` embedding doesn't scale queries with N.

For every list endpoint that embeds a target-aware ``capabilities`` map on
each ChangeSet row, the query count at N=20 rows must equal the query count
at N=2 rows. Narrow scope by design — this catches embed-loop N+1 (e.g. an
accidental ``cs.user`` lookup inside the per-row loop) and nothing else.

The policy's ``ChangeSetPolicyView`` reads only ``id`` and ``actor_id``, which
live on the row itself, so no prefetch helper is needed today. When a future
target Protocol grows a relation, this test fails first.

Each test fetches anonymously, so a session refresh can't perturb the count.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.test_factories import make_user
from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.test_factories import make_claim, user_changeset

pytestmark = pytest.mark.django_db


def _seed_changesets(user, pm, n: int, *, start: int = 0) -> None:
    """Create ``n`` edits on ``pm`` as ``user``, each producing one changeset.

    ``start`` offsets the year so a second call adds genuinely new claim rows
    rather than repeating the first call's values.
    """
    for i in range(start, start + n):
        make_claim(
            pm, "production_year", 1990 + i, user=user, changeset=user_changeset(user)
        )


def _q(fn: Callable[[], object]) -> int:
    with CaptureQueriesContext(connection) as ctx:
        fn()
    return len(ctx.captured_queries)


def _grew_by(base_rows: int, scaled_rows: int, n: int) -> str:
    """Message for the guard that keeps the query-count comparison meaningful."""
    return (
        f"seeded edits are not reaching the response: {base_rows} -> {scaled_rows} "
        f"rows, expected a rise of {n}. The query counts below would be comparing "
        f"two reads of the same size, and would match however the endpoint behaves."
    )


def test_edit_history_capabilities_does_not_scale_queries(client, bootstrap_source):
    """GET /api/pages/edit-history/... query count must not grow with N rows."""
    user = make_user()
    pm = make_machine_model(name="MM", slug="mm-x", production_year=1997)
    make_claim(pm, "name", "MM", ingest_source=bootstrap_source)
    url = f"/api/pages/edit-history/model/{pm.slug}/"

    _seed_changesets(user, pm, 2)
    base_rows = len(client.get(url).json())
    base = _q(lambda: client.get(url))

    _seed_changesets(user, pm, 18, start=2)
    scaled_rows = len(client.get(url).json())
    scaled = _q(lambda: client.get(url))

    assert scaled_rows == base_rows + 18, _grew_by(base_rows, scaled_rows, 18)
    assert scaled == base, (
        f"edit-history embed scales queries with N: {base} -> {scaled}. "
        f"A per-row ``capabilities`` lookup is hitting the DB; either a "
        f"target Protocol read traverses a relation that isn't prefetched, "
        f"or the serializer is doing a DB read inside the loop."
    )


def test_global_changes_feed_capabilities_does_not_scale_queries(
    client, bootstrap_source
):
    """GET /api/pages/changesets/ query count must not grow with N rows."""
    user = make_user()
    pm = make_machine_model(name="MM2", slug="mm-y", production_year=1997)
    make_claim(pm, "name", "MM2", ingest_source=bootstrap_source)
    url = "/api/pages/changesets/"

    _seed_changesets(user, pm, 2)
    base_rows = len(client.get(url).json()["items"])
    base = _q(lambda: client.get(url))

    _seed_changesets(user, pm, 18, start=2)
    scaled_rows = len(client.get(url).json()["items"])
    scaled = _q(lambda: client.get(url))

    assert scaled_rows == base_rows + 18, _grew_by(base_rows, scaled_rows, 18)
    assert scaled == base, (
        f"global changes-feed embed scales queries with N: {base} -> {scaled}."
    )


def test_user_profile_recent_edits_capabilities_does_not_scale_queries(
    client, bootstrap_source
):
    """GET /api/pages/user/{username}/ recent_edits embed must not scale queries."""
    user = make_user()
    pm = make_machine_model(name="MM4", slug="mm-w", production_year=1997)
    make_claim(pm, "name", "MM4", ingest_source=bootstrap_source)
    url = f"/api/pages/user/{user.username}/"

    _seed_changesets(user, pm, 2)
    base_rows = len(client.get(url).json()["recent_edits"])
    base = _q(lambda: client.get(url))

    _seed_changesets(user, pm, 18, start=2)
    scaled_rows = len(client.get(url).json()["recent_edits"])
    scaled = _q(lambda: client.get(url))

    assert scaled_rows == base_rows + 18, _grew_by(base_rows, scaled_rows, 18)
    assert scaled == base, (
        f"user-profile recent_edits embed scales queries with N: {base} -> {scaled}."
    )
