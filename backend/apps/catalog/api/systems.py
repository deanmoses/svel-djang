"""Systems router — list, detail, and claims endpoints."""

from __future__ import annotations

from typing import cast

from django.db.models import Count, F, Max, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.responses import Status
from ninja.security import django_auth

from apps.catalog.naming import normalize_catalog_name
from apps.core.licensing import get_minimum_display_rank
from apps.core.models import active_status_q
from apps.provenance.helpers import claims_prefetch
from apps.provenance.rate_limits import CREATE_RATE_LIMIT_SPEC, check_and_record
from apps.provenance.schemas import EditCitationInput, RichTextSchema
from apps.provenance.typing import HasActiveClaims

from ..models import MachineModel, Manufacturer, System
from ._typing import HasModelCount
from .edit_claims import (
    ClaimSpec,
    StructuredValidationError,
    execute_claims,
    plan_scalar_field_claims,
)
from .entity_create import (
    assert_name_available,
    assert_slug_available,
    create_entity_with_claims,
    validate_name,
    validate_slug_format,
)
from .entity_crud import register_entity_delete_restore
from .helpers import (
    _build_rich_text,
    _extract_image_urls,
)
from .schemas import (
    ClaimPatchSchema,
    Ref,
    RelatedTitleSchema,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SystemListSchema(Schema):
    name: str
    slug: str
    manufacturer: Ref | None = None
    model_count: int = 0


class SystemCreateSchema(Schema):
    name: str
    slug: str
    manufacturer_slug: str
    note: str = ""
    citation: EditCitationInput | None = None


class SiblingSystemSchema(Schema):
    name: str
    slug: str


class SystemDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    manufacturer: Ref | None = None
    technology_subgeneration: Ref | None = None
    titles: list[RelatedTitleSchema]
    sibling_systems: list[SiblingSystemSchema] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _system_detail_qs():
    return (
        System.objects.active()
        .select_related("manufacturer", "technology_subgeneration")
        .prefetch_related(
            claims_prefetch(),
            Prefetch(
                "machine_models",
                queryset=MachineModel.objects.active()
                .filter(variant_of__isnull=True)
                .select_related("corporate_entity__manufacturer", "title")
                .order_by(F("year").desc(nulls_last=True), "name"),
            ),
        )
    )


def _serialize_system_detail(system) -> dict:
    min_rank = get_minimum_display_rank()
    titles: dict[str, dict] = {}
    for m in system.machine_models.all():
        if m.title is None:
            continue
        key = m.title.slug
        if key not in titles:
            thumbnail_url = _extract_image_urls(m.extra_data or {}, min_rank=min_rank)[
                0
            ]
            mfr = (
                m.corporate_entity.manufacturer
                if m.corporate_entity and m.corporate_entity.manufacturer
                else None
            )
            titles[key] = {
                "name": m.title.name,
                "slug": m.title.slug,
                "year": m.year,
                "manufacturer_name": mfr.name if mfr else None,
                "thumbnail_url": thumbnail_url,
            }
        elif titles[key]["thumbnail_url"] is None:
            thumbnail_url = _extract_image_urls(m.extra_data or {}, min_rank=min_rank)[
                0
            ]
            if thumbnail_url:
                titles[key]["thumbnail_url"] = thumbnail_url

    sibling_systems = []
    if system.manufacturer:
        sibling_systems = list(
            System.objects.active()
            .filter(manufacturer=system.manufacturer)
            .exclude(pk=system.pk)
            .annotate(latest_year=Max("machine_models__year"))
            .order_by(F("latest_year").desc(nulls_last=True), "name")
            .values("name", "slug")
        )

    return {
        "name": system.name,
        "slug": system.slug,
        "description": _build_rich_text(
            system, "description", cast(HasActiveClaims, system).active_claims
        ),
        "manufacturer": (
            {"name": system.manufacturer.name, "slug": system.manufacturer.slug}
            if system.manufacturer
            else None
        ),
        "technology_subgeneration": (
            {
                "name": system.technology_subgeneration.name,
                "slug": system.technology_subgeneration.slug,
            }
            if system.technology_subgeneration
            else None
        ),
        "titles": list(titles.values()),
        "sibling_systems": sibling_systems,
    }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

systems_router = Router(tags=["systems"])


@systems_router.get("/all/", response=list[SystemListSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_systems(request):
    """Return every system with machine count (no pagination)."""
    qs = (
        System.objects.active()
        .select_related("manufacturer")
        .annotate(
            model_count=Count(
                "machine_models",
                filter=Q(machine_models__variant_of__isnull=True)
                & active_status_q("machine_models"),
            )
        )
        .order_by("name")
    )
    return [
        {
            "name": s.name,
            "slug": s.slug,
            "manufacturer": (
                {"name": s.manufacturer.name, "slug": s.manufacturer.slug}
                if s.manufacturer
                else None
            ),
            "model_count": cast(HasModelCount, s).model_count,
        }
        for s in qs
    ]


@systems_router.patch(
    "/{slug}/claims/", auth=django_auth, response=SystemDetailSchema, tags=["private"]
)
def patch_system_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    system = get_object_or_404(System.objects.active(), slug=slug)
    specs = plan_scalar_field_claims(System, data.fields, entity=system)

    execute_claims(
        system, specs, user=request.user, note=data.note, citation=data.citation
    )

    system = get_object_or_404(_system_detail_qs(), slug=system.slug)
    return _serialize_system_detail(system)


# ---------------------------------------------------------------------------
# Create / delete / restore wiring
# ---------------------------------------------------------------------------


@systems_router.post(
    "/",
    auth=django_auth,
    response={201: SystemDetailSchema},
    tags=["private"],
)
def create_system(request, data: SystemCreateSchema):
    """Create a new System.

    Required fields: ``name``, ``slug``, ``manufacturer_slug``. Optional
    ``technology_subgeneration`` is deferred to edit — not part of the
    minimum-viable create per ``docs/plans/RecordCreateDelete.md``.

    Bespoke (rather than ``register_entity_create``) because System has a
    required non-URL-nested FK (manufacturer) which the shared registrar
    doesn't express. Uses the same building blocks.
    """
    check_and_record(request.user, CREATE_RATE_LIMIT_SPEC)

    name_max = System._meta.get_field("name").max_length
    name = validate_name(data.name, max_length=name_max)
    slug = validate_slug_format(data.slug)

    manufacturer_slug = (data.manufacturer_slug or "").strip()
    if not manufacturer_slug:
        raise StructuredValidationError(
            message="Manufacturer is required.",
            field_errors={"manufacturer_slug": "Manufacturer is required."},
        )
    manufacturer = Manufacturer.objects.active().filter(slug=manufacturer_slug).first()
    if manufacturer is None:
        raise StructuredValidationError(
            message="Manufacturer not found.",
            field_errors={"manufacturer_slug": "Manufacturer not found."},
        )

    # ``include_deleted=True`` is load-bearing: ``System.name`` is
    # ``unique=True`` at the DB level, so a name that collides with a
    # soft-deleted System would otherwise pass the active-only pre-check
    # and trip the DB unique constraint, which
    # ``create_entity_with_claims`` misreports as a slug collision.
    assert_name_available(
        System,
        name,
        normalize=normalize_catalog_name,
        friendly_label="system",
        include_deleted=True,
    )
    assert_slug_available(System, slug)

    create_entity_with_claims(
        System,
        row_kwargs={
            "name": name,
            "slug": slug,
            "status": "active",
            "manufacturer": manufacturer,
        },
        claim_specs=[
            ClaimSpec(field_name="name", value=name),
            ClaimSpec(field_name="slug", value=slug),
            ClaimSpec(field_name="status", value="active"),
            # FK claim value is the parent's slug string.
            ClaimSpec(field_name="manufacturer", value=manufacturer.slug),
        ],
        user=request.user,
        note=data.note,
        citation=data.citation,
    )

    created = get_object_or_404(_system_detail_qs(), slug=slug)
    return Status(201, _serialize_system_detail(created))


register_entity_delete_restore(
    systems_router,
    System,
    detail_qs=_system_detail_qs,
    serialize_detail=_serialize_system_detail,
    response_schema=SystemDetailSchema,
)
