"""People router — list, detail, and claim-patch endpoints."""

from __future__ import annotations

from typing import Optional

from django.db.models import Count, F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from ..cache import PEOPLE_ALL_KEY, get_cached_response, set_cached_response
from .constants import DEFAULT_PAGE_SIZE
from apps.provenance.helpers import build_sources, claims_prefetch

from .helpers import (
    _build_rich_text,
    _extract_image_urls,
    _media_prefetch,
    _serialize_uploaded_media,
)
from .schemas import (
    ClaimPatchSchema,
    ClaimSchema,
    RelatedTitleSchema,
    RichTextSchema,
    UploadedMediaSchema,
)

from apps.core.licensing import get_minimum_display_rank

from ..models import Credit, MachineModel, Person
from .edit_claims import execute_claims, plan_scalar_field_claims

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PersonGridSchema(Schema):
    name: str
    slug: str
    credit_count: int = 0
    thumbnail_url: Optional[str] = None


class PersonSchema(Schema):
    name: str
    slug: str
    credit_count: int = 0


class PersonTitleSchema(RelatedTitleSchema):
    roles: list[str] = []


class PersonDetailSchema(Schema):
    name: str
    slug: str
    description: RichTextSchema = RichTextSchema()
    birth_year: int | None = None
    birth_month: int | None = None
    birth_day: int | None = None
    death_year: int | None = None
    death_month: int | None = None
    death_day: int | None = None
    birth_place: str | None = None
    nationality: str | None = None
    photo_url: str | None = None
    titles: list[PersonTitleSchema]
    uploaded_media: list[UploadedMediaSchema] = []
    sources: list[ClaimSchema]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_person_detail(person) -> dict:
    """Serialize a Person into the detail response dict.

    Expects *person* to have been fetched with prefetch_related for credits
    (select_related model, model__title, model__manufacturer) and claims
    (to_attr="active_claims").
    """
    min_rank = get_minimum_display_rank()
    titles: dict[str, dict] = {}
    for c in person.credits.all():
        if c.model is None or c.model.title is None:
            continue
        title = c.model.title
        key = title.slug
        if key not in titles:
            thumbnail_url = _extract_image_urls(
                c.model.extra_data or {}, min_rank=min_rank
            )[0]
            titles[key] = {
                "name": title.name,
                "slug": title.slug,
                "year": c.model.year,
                "manufacturer_name": (
                    c.model.corporate_entity.manufacturer.name
                    if c.model.corporate_entity
                    and c.model.corporate_entity.manufacturer
                    else None
                ),
                "thumbnail_url": thumbnail_url,
                "roles": [],
            }
        elif titles[key]["thumbnail_url"] is None:
            thumbnail_url = _extract_image_urls(
                c.model.extra_data or {}, min_rank=min_rank
            )[0]
            if thumbnail_url:
                titles[key]["thumbnail_url"] = thumbnail_url
        role_display = c.role.name
        if role_display not in titles[key]["roles"]:
            titles[key]["roles"].append(role_display)
    return {
        "name": person.name,
        "slug": person.slug,
        "description": _build_rich_text(
            person, "description", getattr(person, "active_claims", [])
        ),
        "birth_year": person.birth_year,
        "birth_month": person.birth_month,
        "birth_day": person.birth_day,
        "death_year": person.death_year,
        "death_month": person.death_month,
        "death_day": person.death_day,
        "birth_place": person.birth_place,
        "nationality": person.nationality,
        "photo_url": person.photo_url,
        "titles": list(titles.values()),
        "uploaded_media": _serialize_uploaded_media(
            getattr(person, "all_media", None) or []
        ),
        "sources": build_sources(getattr(person, "active_claims", [])),
    }


def _person_qs():
    return Person.objects.active().prefetch_related(
        Prefetch(
            "credits",
            queryset=Credit.objects.filter(model__isnull=False)
            .select_related(
                "model__title", "model__corporate_entity__manufacturer", "role"
            )
            .order_by(F("model__year").desc(nulls_last=True), "model__name"),
        ),
        claims_prefetch(),
        _media_prefetch(),
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

people_router = Router(tags=["people"])


@people_router.get("/", response=list[PersonSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_people(request):
    return list(
        Person.objects.active()
        .annotate(credit_count=Count("credits"))
        .order_by("name")
        .values("name", "slug", "credit_count")
    )


@people_router.get("/all/", response=list[PersonGridSchema])
@decorate_view(cache_control(no_cache=True))
def list_all_people(request):
    """Return every person with credit count and thumbnail.

    Uses a bulk query to find the newest credited model per person for
    thumbnails, instead of prefetching all credits and iterating in Python.
    See ``list_all_titles`` for the full explanation of this pattern.
    """
    response = get_cached_response(PEOPLE_ALL_KEY)
    if response is not None:
        return response

    min_rank = get_minimum_display_rank()

    people = list(
        Person.objects.active()
        .annotate(credit_count=Count("credits"))
        .order_by("-credit_count")
    )

    # Batch thumbnail: newest credited model with extra_data per person
    person_thumb_model: dict[int, int] = {}
    for person_id, model_id in (
        Credit.objects.filter(
            model__isnull=False,
            model__extra_data__isnull=False,
        )
        .order_by(F("model__year").desc(nulls_last=True))
        .values_list("person_id", "model_id")
    ):
        if person_id not in person_thumb_model:
            person_thumb_model[person_id] = model_id
    thumb_models = {
        m.id: m
        for m in MachineModel.objects.filter(
            id__in=set(person_thumb_model.values())
        ).only("id", "extra_data")
    }

    result = []
    for p in people:
        thumb = None
        tm_id = person_thumb_model.get(p.id)
        tm = thumb_models.get(tm_id) if tm_id else None
        if tm and tm.extra_data:
            t, _ = _extract_image_urls(tm.extra_data, min_rank=min_rank)
            if t:
                thumb = t
        result.append(
            {
                "name": p.name,
                "slug": p.slug,
                "credit_count": p.credit_count,
                "thumbnail_url": thumb,
            }
        )
    return set_cached_response(PEOPLE_ALL_KEY, result)


@people_router.patch(
    "/{slug}/claims/", auth=django_auth, response=PersonDetailSchema, tags=["private"]
)
def patch_person_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    person = get_object_or_404(Person.objects.active(), slug=slug)

    specs = plan_scalar_field_claims(Person, data.fields, entity=person)

    execute_claims(
        person, specs, user=request.user, note=data.note, citation=data.citation
    )

    person = get_object_or_404(_person_qs(), slug=person.slug)
    return _serialize_person_detail(person)
