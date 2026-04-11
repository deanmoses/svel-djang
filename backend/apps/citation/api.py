"""API endpoints for the citation app.

Routers: citation_sources.
Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

from typing import Optional

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.responses import Status
from ninja.security import django_auth
from pydantic import field_validator

from .models import CitationSource, CitationSourceLink

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

citation_sources_router = Router(tags=["citation-sources", "private"])

routers = [
    ("/citation-sources/", citation_sources_router),
]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

NONNULLABLE_STR_FIELDS = (
    "name",
    "source_type",
    "author",
    "publisher",
    "date_note",
    "description",
)


class CitationSourceSearchSchema(Schema):
    id: int
    name: str
    source_type: str
    author: str
    publisher: str
    year: Optional[int] = None
    isbn: Optional[str] = None
    parent_id: Optional[int] = None
    has_children: bool = False
    is_abstract: bool = False
    skip_locator: bool = False
    child_input_mode: Optional[str] = None
    identifier_key: str = ""


class CitationSourceCreateSchema(Schema):
    name: str
    source_type: str
    author: str = ""
    publisher: str = ""
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    date_note: str = ""
    isbn: Optional[str] = None
    description: str = ""
    parent_id: Optional[int] = None
    # Optional: atomically create a CitationSourceLink alongside the source.
    url: Optional[str] = None
    link_label: str = ""
    link_type: str = "homepage"

    @field_validator("isbn", mode="before")
    @classmethod
    def coerce_empty_isbn_to_none(cls, v):
        """Empty string → None for nullable unique field."""
        return None if v == "" else v


class CitationSourceUpdateSchema(Schema):
    name: Optional[str] = None
    source_type: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    date_note: Optional[str] = None
    isbn: Optional[str] = None
    description: Optional[str] = None

    @field_validator(*NONNULLABLE_STR_FIELDS, mode="before")
    @classmethod
    def coerce_null_to_empty(cls, v):
        """None → empty string for non-nullable CharFields."""
        return "" if v is None else v

    @field_validator("isbn", mode="before")
    @classmethod
    def coerce_empty_isbn_to_none(cls, v):
        """Empty string → None for nullable unique field."""
        return None if v == "" else v


class CitationSourceParentSchema(Schema):
    id: int
    name: str


class CitationSourceChildSchema(Schema):
    id: int
    name: str
    source_type: str
    year: Optional[int] = None
    isbn: Optional[str] = None
    skip_locator: bool = False
    urls: list[str] = []


class CitationSourceLinkSchema(Schema):
    id: int
    link_type: str
    url: str
    label: str


class CitationSourceDetailSchema(Schema):
    id: int
    name: str
    source_type: str
    author: str
    publisher: str
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    date_note: str
    isbn: Optional[str] = None
    description: str
    identifier_key: str = ""
    skip_locator: bool = False
    parent: Optional[CitationSourceParentSchema] = None
    links: list[CitationSourceLinkSchema] = []
    children: list[CitationSourceChildSchema] = []
    created_at: str
    updated_at: str


class CitationSourceLinkCreateSchema(Schema):
    link_type: str
    url: str
    label: str = ""


class CitationSourceLinkUpdateSchema(Schema):
    link_type: Optional[str] = None
    url: Optional[str] = None
    label: Optional[str] = None

    @field_validator("label", mode="before")
    @classmethod
    def coerce_null_to_empty(cls, v):
        return "" if v is None else v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skip_locator(source_type, parent_id):
    """Web children skip the locator stage (their URL is the locator)."""
    return source_type == "web" and parent_id is not None


def _is_abstract(source_type, parent_id, has_children):
    """Source is abstract if it has children or is a root web/magazine source."""
    return has_children or (parent_id is None and source_type in ("web", "magazine"))


def _child_input_mode(source_type, parent_id, has_children):
    """How the frontend should identify a child: search, enter ID, or N/A."""
    if not _is_abstract(source_type, parent_id, has_children):
        return None
    return "enter_identifier" if source_type == "web" else "search_children"


def _clean_and_save(instance, update_fields=None, *, integrity_msg=""):
    """Validate model then save.

    Converts both ``ValidationError`` (from ``full_clean``) and
    ``IntegrityError`` (from ``save``) into ``HttpError(422)``.

    *integrity_msg* is the friendly message shown when the expected unique
    constraint fires.  For unexpected integrity violations the raw DB
    message is surfaced instead.
    """
    try:
        instance.full_clean()
    except ValidationError as exc:
        if hasattr(exc, "message_dict"):
            parts = []
            for field, messages in exc.message_dict.items():
                for msg in messages:
                    parts.append(f"{field}: {msg}" if field != "__all__" else msg)
            detail = "; ".join(parts)
        else:
            detail = str(exc)
        raise HttpError(422, detail)
    try:
        instance.save(update_fields=update_fields)
    except IntegrityError as exc:
        msg = str(exc).lower()
        if integrity_msg and ("unique" in msg or "duplicate" in msg):
            raise HttpError(422, integrity_msg)
        raise HttpError(422, f"Integrity error: {exc}")


def _detail_qs():
    return CitationSource.objects.select_related("parent").prefetch_related(
        "links", "children", "children__links"
    )


def _serialize_detail(source) -> dict:
    parent = None
    if source.parent_id is not None:
        parent = {"id": source.parent_id, "name": source.parent.name}
    return {
        "id": source.pk,
        "name": source.name,
        "source_type": source.source_type,
        "author": source.author,
        "publisher": source.publisher,
        "year": source.year,
        "month": source.month,
        "day": source.day,
        "date_note": source.date_note,
        "isbn": source.isbn,
        "description": source.description,
        "identifier_key": source.identifier_key,
        "skip_locator": _skip_locator(source.source_type, source.parent_id),
        "parent": parent,
        "links": [
            CitationSourceLinkSchema.from_orm(link).model_dump()
            for link in source.links.all()
        ],
        "children": [
            {
                "id": child.pk,
                "name": child.name,
                "source_type": child.source_type,
                "year": child.year,
                "isbn": child.isbn,
                "skip_locator": _skip_locator(child.source_type, child.parent_id),
                "urls": [link.url for link in child.links.all()],
            }
            for child in source.children.all()
        ],
        "created_at": source.created_at.isoformat(),
        "updated_at": source.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Citation Source endpoints
# ---------------------------------------------------------------------------


@citation_sources_router.get(
    "/search/",
    response=list[CitationSourceSearchSchema],
    auth=django_auth,
)
def search_citation_sources(request, q: str = ""):
    """Typeahead search across name, author, publisher, isbn, and linked URLs."""
    q = q.strip()
    if not q:
        return []
    qs = (
        CitationSource.objects.filter(
            Q(name__icontains=q)
            | Q(author__icontains=q)
            | Q(publisher__icontains=q)
            | Q(isbn__icontains=q)
            | Q(links__url__icontains=q)
        )
        .annotate(
            has_children=Exists(CitationSource.objects.filter(parent=OuterRef("pk")))
        )
        .distinct()
        .order_by("name")[:20]
    )
    return [
        {
            "id": s.pk,
            "name": s.name,
            "source_type": s.source_type,
            "author": s.author,
            "publisher": s.publisher,
            "year": s.year,
            "isbn": s.isbn,
            "parent_id": s.parent_id,
            "has_children": s.has_children,
            "is_abstract": _is_abstract(s.source_type, s.parent_id, s.has_children),
            "skip_locator": _skip_locator(s.source_type, s.parent_id),
            "child_input_mode": _child_input_mode(
                s.source_type, s.parent_id, s.has_children
            ),
            "identifier_key": s.identifier_key,
        }
        for s in qs
    ]


@citation_sources_router.post(
    "/",
    response={201: CitationSourceDetailSchema},
    auth=django_auth,
)
def create_citation_source(request, data: CitationSourceCreateSchema):
    """Create a new Citation Source, optionally with an initial link."""
    parent = None
    if data.parent_id is not None:
        parent = get_object_or_404(CitationSource, pk=data.parent_id)

    with transaction.atomic():
        source = CitationSource(
            name=data.name,
            source_type=data.source_type,
            author=data.author,
            publisher=data.publisher,
            year=data.year,
            month=data.month,
            day=data.day,
            date_note=data.date_note,
            isbn=data.isbn,
            description=data.description,
            parent=parent,
            created_by=request.user,
            updated_by=request.user,
        )
        _clean_and_save(source, integrity_msg="A source with this ISBN already exists.")

        if data.url:
            link = CitationSourceLink(
                citation_source=source,
                link_type=data.link_type,
                url=data.url,
                label=data.link_label,
                created_by=request.user,
                updated_by=request.user,
            )
            _clean_and_save(link)

    source = get_object_or_404(_detail_qs(), pk=source.pk)
    return Status(201, _serialize_detail(source))


@citation_sources_router.get(
    "/{source_id}/children/",
    response=list[CitationSourceChildSchema],
    auth=django_auth,
)
def list_citation_source_children(request, source_id: int, q: str = ""):
    """Filtered children of a source, searched by name or linked URL."""
    parent = get_object_or_404(CitationSource, pk=source_id)
    q = q.strip()
    if not q:
        return []
    children = (
        CitationSource.objects.filter(parent=parent)
        .filter(Q(name__icontains=q) | Q(links__url__icontains=q))
        .prefetch_related("links")
        .distinct()
        .order_by("name")[:20]
    )
    return [
        {
            "id": child.pk,
            "name": child.name,
            "source_type": child.source_type,
            "year": child.year,
            "isbn": child.isbn,
            "skip_locator": _skip_locator(child.source_type, child.parent_id),
            "urls": [link.url for link in child.links.all()],
        }
        for child in children
    ]


@citation_sources_router.get(
    "/{source_id}/",
    response=CitationSourceDetailSchema,
    auth=django_auth,
)
def get_citation_source(request, source_id: int):
    """Get a Citation Source with its links and children."""
    source = get_object_or_404(_detail_qs(), pk=source_id)
    return _serialize_detail(source)


@citation_sources_router.patch(
    "/{source_id}/",
    response=CitationSourceDetailSchema,
    auth=django_auth,
)
def update_citation_source(request, source_id: int, data: CitationSourceUpdateSchema):
    """Partially update a Citation Source."""
    source = get_object_or_404(CitationSource, pk=source_id)
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        raise HttpError(422, "No changes provided.")

    for attr, value in fields.items():
        setattr(source, attr, value)
    source.updated_by = request.user

    _clean_and_save(
        source,
        update_fields=[*fields.keys(), "updated_by", "updated_at"],
        integrity_msg="A source with this ISBN already exists.",
    )

    source = get_object_or_404(_detail_qs(), pk=source.pk)
    return _serialize_detail(source)


# ---------------------------------------------------------------------------
# Citation Source Link endpoints
# ---------------------------------------------------------------------------


@citation_sources_router.post(
    "/{source_id}/links/",
    response={201: CitationSourceLinkSchema},
    auth=django_auth,
)
def create_citation_source_link(
    request, source_id: int, data: CitationSourceLinkCreateSchema
):
    """Create a link on a Citation Source."""
    source = get_object_or_404(CitationSource, pk=source_id)
    link = CitationSourceLink(
        citation_source=source,
        link_type=data.link_type,
        url=data.url,
        label=data.label,
        created_by=request.user,
        updated_by=request.user,
    )
    _clean_and_save(link, integrity_msg="This URL is already linked to this source.")

    return Status(201, link)


@citation_sources_router.patch(
    "/{source_id}/links/{link_id}/",
    response=CitationSourceLinkSchema,
    auth=django_auth,
)
def update_citation_source_link(
    request, source_id: int, link_id: int, data: CitationSourceLinkUpdateSchema
):
    """Partially update a link on a Citation Source."""
    link = get_object_or_404(
        CitationSourceLink, pk=link_id, citation_source_id=source_id
    )
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        raise HttpError(422, "No changes provided.")

    for attr, value in fields.items():
        setattr(link, attr, value)
    link.updated_by = request.user

    _clean_and_save(
        link,
        update_fields=[*fields.keys(), "updated_by", "updated_at"],
        integrity_msg="This URL is already linked to this source.",
    )

    return link
