"""API endpoints for the core app.

Router: link_types — wikilink autocomplete support.
Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q
from django.http import HttpRequest
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.markdown_links import get_autocomplete_types, get_link_type

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

AUTOCOMPLETE_RESULT_LIMIT = 20


class LinkTypeSchema(Schema):
    name: str
    label: str
    description: str
    flow: str


class LinkTargetSchema(Schema):
    ref: str
    label: str


class LinkTargetsResponseSchema(Schema):
    results: list[LinkTargetSchema]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

link_types_router = Router(tags=["private"])


@link_types_router.get("/", response=list[LinkTypeSchema])
def list_link_types(request: HttpRequest) -> list[Any]:
    """Return all link types that support autocomplete, for the type picker."""
    return get_autocomplete_types()


@link_types_router.get("/targets/", response=LinkTargetsResponseSchema)
def search_link_targets(
    request: HttpRequest,
    type: str,
    q: str = "",
) -> dict[str, list[dict[str, str]]]:
    """Search within a link type for autocomplete results."""
    lt = get_link_type(type)
    if lt is None or not lt.is_enabled() or not lt.autocomplete_serialize:
        raise HttpError(400, f"Invalid or unsupported link type: {type!r}")

    model = lt.get_model()

    # Use .active() when available (EntityStatusMixin models) to exclude
    # soft-deleted entities; fall back to .all() for models without it.
    qs = (
        model.objects.active()
        if hasattr(model.objects, "active")
        else model.objects.all()
    )

    if lt.autocomplete_select_related:
        qs = qs.select_related(*lt.autocomplete_select_related)

    if lt.autocomplete_ordering:
        qs = qs.order_by(*lt.autocomplete_ordering)

    if q and lt.autocomplete_search_fields:
        q_filter = Q()
        for field in lt.autocomplete_search_fields:
            q_filter |= Q(**{field: q})
        qs = qs.filter(q_filter)

    results = [lt.autocomplete_serialize(obj) for obj in qs[:AUTOCOMPLETE_RESULT_LIMIT]]
    return {"results": results}


routers = [
    ("/link-types/", link_types_router),
]
