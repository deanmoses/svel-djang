"""API endpoints for the core app.

Router: link_types — wikilink autocomplete support.
Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.core.schemas import (
    LinkTargetListSchema,
    LinkTypeSchema,
)
from apps.core.wikilinks import get_picker_type, get_picker_types

AUTOCOMPLETE_RESULT_LIMIT = 20


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

link_types_router = Router(tags=["private"])


@link_types_router.get("/", response=list[LinkTypeSchema])
def list_link_types(request: HttpRequest) -> list[dict[str, str]]:
    """Return all link types offered in the wikilink picker."""
    return get_picker_types()


@link_types_router.get("/targets/", response=LinkTargetListSchema)
def search_link_targets(
    request: HttpRequest,
    type: str,
    q: str = "",
) -> LinkTargetListSchema:
    """Search within a picker type for autocomplete results.

    Standard-flow types only — custom-flow picker types (citations) drive
    their own frontend flow and never hit this endpoint.
    """
    pt = get_picker_type(type)
    if (
        pt is None
        or not pt.is_enabled()
        or pt.flow != "standard"
        or pt.autocomplete_serialize is None
    ):
        raise HttpError(400, f"Invalid or unsupported link type: {type!r}")

    model = pt.get_model()

    # Use .active() when available (LifecycleStatusModel models) to exclude
    # soft-deleted entities; fall back to .all() for models without it.
    qs = (
        model.objects.active()
        if hasattr(model.objects, "active")
        else model.objects.all()
    )

    if pt.autocomplete_select_related:
        qs = qs.select_related(*pt.autocomplete_select_related)

    if pt.autocomplete_ordering:
        qs = qs.order_by(*pt.autocomplete_ordering)

    if q and pt.autocomplete_search_fields:
        q_filter = Q()
        for field in pt.autocomplete_search_fields:
            q_filter |= Q(**{field: q})
        qs = qs.filter(q_filter)

    results = [pt.autocomplete_serialize(obj) for obj in qs[:AUTOCOMPLETE_RESULT_LIMIT]]
    return LinkTargetListSchema(results=results)


routers = [
    ("/link-types/", link_types_router),
]
