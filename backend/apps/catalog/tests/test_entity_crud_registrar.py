"""Focused tests for the ``register_entity_create`` registrar.

The behavioral test for ``scope_filter_builder`` lives alongside the first
real caller (CorporateEntity create, Manufacturer/CE plan). This file
covers the contract guards that don't depend on a live parent model.
"""

from __future__ import annotations

import pytest
from django.db.models import Q
from ninja import Router, Schema

from apps.catalog.api.entity_crud import register_entity_create
from apps.catalog.models import Theme


class DummySchema(Schema):
    pass


def test_scope_filter_builder_requires_parent_field():
    """``scope_filter_builder`` is meaningful only in parented mode; pair
    it with a non-parented registration and the registrar raises, not the
    first incoming request."""
    router = Router()
    with pytest.raises(TypeError, match="scope_filter_builder requires parent_field"):
        register_entity_create(
            router,
            Theme,
            detail_qs=lambda: Theme.objects.all(),
            serialize_detail=lambda _t: DummySchema(),
            response_schema=DummySchema,  # dummy; never reached
            scope_filter_builder=lambda _p: Q(),
        )


def test_parented_without_parent_model_still_raises():
    """Existing guard: parent_field without parent_model / route_suffix."""
    router = Router()
    with pytest.raises(TypeError, match="parent_model and route_suffix are required"):
        register_entity_create(
            router,
            Theme,
            detail_qs=lambda: Theme.objects.all(),
            serialize_detail=lambda _t: DummySchema(),
            response_schema=DummySchema,
            parent_field="parent",
        )
