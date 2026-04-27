"""Pagination subclass that names its OpenAPI input component.

Ninja's ``PageNumberPagination.Input`` inner Schema is registered as an
OpenAPI component with the literal name ``Input`` — too generic at the
component level and a naming collision risk. This subclass overrides
``Input`` with a renamed inner Schema so the component is registered as
``PaginationParamsSchema``.
"""

from __future__ import annotations

from ninja import Field, Schema
from ninja.pagination import PageNumberPagination


class NamedPageNumberPagination(PageNumberPagination):
    class PaginationParamsSchema(Schema):
        page: int = Field(1, ge=1)
        page_size: int | None = Field(None, ge=1)

    Input = PaginationParamsSchema  # type: ignore[assignment]
