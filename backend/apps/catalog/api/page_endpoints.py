"""Page-oriented endpoints for catalog entities.

These endpoints live under /api/pages/ and are tagged "private" so they
stay out of the public API docs.  They return page-model responses shaped
for specific SvelteKit SSR routes.

Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router

from .machine_models import (
    MachineModelDetailSchema,
    _model_detail_qs,
    _serialize_model_detail,
)
from .manufacturers import (
    ManufacturerDetailSchema,
    _manufacturer_qs,
    _serialize_manufacturer_detail,
)
from .titles import TitleDetailSchema, _detail_qs, _serialize_title_detail

pages_router = Router(tags=["private"])


@pages_router.get("/title/{slug}", response=TitleDetailSchema)
def title_detail_page(request, slug: str):
    title = get_object_or_404(_detail_qs(), slug=slug)
    return _serialize_title_detail(title)


@pages_router.get("/manufacturer/{slug}", response=ManufacturerDetailSchema)
def manufacturer_detail_page(request, slug: str):
    mfr = get_object_or_404(_manufacturer_qs(), slug=slug)
    return _serialize_manufacturer_detail(mfr)


@pages_router.get("/model/{slug}", response=MachineModelDetailSchema)
def model_detail_page(request, slug: str):
    pm = get_object_or_404(_model_detail_qs(), slug=slug)
    return _serialize_model_detail(pm)
