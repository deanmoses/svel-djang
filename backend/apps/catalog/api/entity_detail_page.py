"""Shared SSR-detail-page registrar for any ``LinkableModel`` subclass.

Mounts ``GET /{entity_type}/{public_id}`` on a Ninja router. The route
segment comes from ``model_cls.entity_type``; the lookup field from
``model_cls.public_id_field``. ``{public_id}`` uses the Ninja ``path``
converter so multi-segment ids (Location) round-trip through one
registration.

Used exclusively by :mod:`apps.catalog.api.page_endpoints`; lives next
to :mod:`apps.catalog.api.entity_crud` because the contract over
``LinkableModel`` is the same, but the read path shares no helpers with
the write registrars and stays in its own module.
"""

from __future__ import annotations

from collections.abc import Callable

from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from apps.catalog.models import CatalogModel


def register_entity_detail_page[ModelT: CatalogModel, SchemaT: Schema](
    router: Router,
    model_cls: type[ModelT],
    *,
    detail_qs: Callable[[], QuerySet[ModelT]],
    serialize_detail: Callable[[ModelT], SchemaT],
    response_schema: type[SchemaT],
) -> None:
    """Mount ``GET /{entity_type}/{public_id}`` on *router*.

    Replaces the per-entity boilerplate of ``get_object_or_404`` +
    serializer + response_schema for SSR detail pages mounted under
    ``/api/pages/``.
    """
    entity_type = model_cls.entity_type
    public_id_field = model_cls.public_id_field

    def _detail(request: HttpRequest, public_id: str) -> SchemaT:
        _ = request
        obj = get_object_or_404(detail_qs(), **{public_id_field: public_id})
        return serialize_detail(obj)

    _detail.__name__ = f"{entity_type.replace('-', '_')}_detail_page"
    router.get(
        f"/{entity_type}/{{path:public_id}}",
        response=response_schema,
    )(_detail)
