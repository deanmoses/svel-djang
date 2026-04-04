"""Cursor-based pagination for newest-first feeds.

Keyed on (created_at, id) to avoid the shifting-window problem
inherent in offset pagination on mutable feeds.
"""

from __future__ import annotations

from datetime import datetime

from django.db.models import Q, QuerySet


def cursor_paginate(
    queryset: QuerySet,
    cursor: str,
    limit: int,
) -> tuple[list, str | None]:
    """Apply keyset pagination to a queryset ordered by (-created_at, -id).

    Returns (items, next_cursor).  ``next_cursor`` is ``None`` when there
    are no more results.

    The cursor is an opaque string with format ``{iso_datetime}|{id}``.
    """
    queryset = queryset.order_by("-created_at", "-id")

    if cursor:
        try:
            ts_str, pk_str = cursor.split("|", 1)
            # The + in timezone offset (+00:00) gets URL-decoded as a space.
            cursor_dt = datetime.fromisoformat(ts_str.replace(" ", "+"))
            cursor_id = int(pk_str)
        except ValueError, IndexError:
            return [], None
        queryset = queryset.filter(
            Q(created_at__lt=cursor_dt) | Q(created_at=cursor_dt, id__lt=cursor_id)
        )

    rows = list(queryset[: limit + 1])

    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.pk}"
    else:
        next_cursor = None

    return rows, next_cursor
