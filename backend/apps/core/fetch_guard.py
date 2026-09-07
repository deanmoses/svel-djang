"""Helper for turning an on-demand field fetch into a hard test failure.

A query-count regression test proves the response's query count doesn't grow
with the row count, which catches an N+1 only once the loop runs more than
once. A lazy load that fires a fixed number of times per request — a
``str(instance)`` on an unfetched FK outside the per-row loop, a deferred
field read during serialization — costs a query on every request and no
count comparison will ever notice.

Blocking the fetch names the model and field at the moment it is touched,
which is the information a bare count is missing.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from django.db.models import FETCH_RAISE
from django.db.models import query as query_module


@contextmanager
def block_lazy_fetches() -> Iterator[None]:
    """Raise ``FieldFetchBlocked`` on any on-demand fetch inside the block.

    Django stamps each instance with the fetch mode of the QuerySet that
    produced it, so overriding the module-level default is what reaches
    querysets built deep inside a view — the ones an HTTP-level test has no
    handle on. ``QuerySet.fetch_mode()`` is the equivalent for a queryset the
    caller builds itself.

    Wrap only the request under measurement. Factories and fixtures lazy-load
    by design, and blocking them reports setup noise rather than an N+1.
    """
    original = query_module.DEFAULT_FETCH_MODE
    query_module.DEFAULT_FETCH_MODE = FETCH_RAISE
    try:
        yield
    finally:
        query_module.DEFAULT_FETCH_MODE = original
