"""People router — list, detail, and claim-patch endpoints."""

from __future__ import annotations

from typing import Optional

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Prefetch
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import cache_control
from ninja import Router, Schema
from ninja.decorators import decorate_view
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate
from ninja.security import django_auth

from apps.core.markdown import render_markdown_fields

from ..cache import PEOPLE_ALL_KEY, invalidate_all
from .constants import DEFAULT_PAGE_SIZE
from .helpers import _build_activity, _claims_prefetch, _extract_image_urls
from .schemas import ClaimPatchSchema, ClaimSchema, RelatedTitleSchema

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
    bio: str
    bio_html: str = ""
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
    activity: list[ClaimSchema]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_person_detail(person) -> dict:
    """Serialize a Person into the detail response dict.

    Expects *person* to have been fetched with prefetch_related for credits
    (select_related model, model__title, model__manufacturer) and claims
    (to_attr="active_claims").
    """
    titles: dict[str, dict] = {}
    for c in person.credits.all():
        if c.model is None or c.model.title is None:
            continue
        title = c.model.title
        key = title.slug
        if key not in titles:
            thumbnail_url = _extract_image_urls(c.model.extra_data or {})[0]
            titles[key] = {
                "name": title.name,
                "slug": title.slug,
                "year": c.model.year,
                "manufacturer_name": (
                    c.model.manufacturer.name if c.model.manufacturer else None
                ),
                "thumbnail_url": thumbnail_url,
                "roles": [],
            }
        elif titles[key]["thumbnail_url"] is None:
            thumbnail_url = _extract_image_urls(c.model.extra_data or {})[0]
            if thumbnail_url:
                titles[key]["thumbnail_url"] = thumbnail_url
        role_display = c.role.name
        if role_display not in titles[key]["roles"]:
            titles[key]["roles"].append(role_display)
    return {
        "name": person.name,
        "slug": person.slug,
        "bio": person.bio,
        **render_markdown_fields(person),
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
        "activity": _build_activity(getattr(person, "active_claims", [])),
    }


def _person_qs():
    from ..models import Credit, Person

    return Person.objects.prefetch_related(
        Prefetch(
            "credits",
            queryset=Credit.objects.filter(model__isnull=False)
            .select_related("model__title", "model__manufacturer", "role")
            .order_by(F("model__year").desc(nulls_last=True), "model__name"),
        ),
        _claims_prefetch(),
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

people_router = Router(tags=["people"])


@people_router.get("/", response=list[PersonSchema])
@paginate(PageNumberPagination, page_size=DEFAULT_PAGE_SIZE)
def list_people(request):
    from ..models import Person

    return list(
        Person.objects.annotate(credit_count=Count("credits"))
        .order_by("name")
        .values("name", "slug", "credit_count")
    )


@people_router.get("/all/", response=list[PersonGridSchema])
@decorate_view(cache_control(public=True, max_age=300))
def list_all_people(request):
    """Return every person with credit count and thumbnail (no pagination)."""
    result = cache.get(PEOPLE_ALL_KEY)
    if result is not None:
        return result

    from ..models import Person

    people = list(
        Person.objects.annotate(credit_count=Count("credits"))
        .prefetch_related("credits__model")
        .order_by("-credit_count")
    )
    result = []
    for p in people:
        thumb = None
        # Thumbnail from most recent credited machine with image data.
        for c in sorted(
            (c for c in p.credits.all() if c.model is not None),
            key=lambda c: c.model.year or 0,
            reverse=True,
        ):
            if c.model.extra_data:
                t, _ = _extract_image_urls(c.model.extra_data)
                if t:
                    thumb = t
                    break
        result.append(
            {
                "name": p.name,
                "slug": p.slug,
                "credit_count": p.credit_count,
                "thumbnail_url": thumb,
            }
        )
    cache.set(PEOPLE_ALL_KEY, result, timeout=None)
    return result


@people_router.get("/{slug}", response=PersonDetailSchema)
@decorate_view(cache_control(public=True, max_age=300))
def get_person(request, slug: str):
    person = get_object_or_404(_person_qs(), slug=slug)
    return _serialize_person_detail(person)


@people_router.patch(
    "/{slug}/claims/", auth=django_auth, response=PersonDetailSchema, tags=["private"]
)
def patch_person_claims(request, slug: str, data: ClaimPatchSchema):
    """Assert per-field claims from the authenticated user, then re-resolve."""
    from apps.core.markdown_links import prepare_markdown_claim_value
    from apps.provenance.models import Claim

    from ..models import Person
    from ..resolve import PERSON_DIRECT_FIELDS, resolve_person

    editable_fields = set(PERSON_DIRECT_FIELDS.keys())
    unknown = set(data.fields.keys()) - editable_fields
    if unknown:
        raise HttpError(422, f"Unknown or non-editable fields: {sorted(unknown)}")

    person = get_object_or_404(Person, slug=slug)

    for field_name, value in data.fields.items():
        try:
            value = prepare_markdown_claim_value(field_name, value, Person)
        except ValidationError as exc:
            raise HttpError(422, "; ".join(exc.messages)) from exc
        Claim.objects.assert_claim(person, field_name, value, user=request.user)

    resolve_person(person)
    invalidate_all()

    person = get_object_or_404(_person_qs(), slug=person.slug)
    return _serialize_person_detail(person)
