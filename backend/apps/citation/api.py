"""API endpoints for the citation app.

Routers: citation_sources.
Auto-discovered via the ``routers`` list convention in config/api.py.
"""

from __future__ import annotations

from dataclasses import asdict

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.responses import Status
from ninja.security import django_auth
from ninja.throttling import AuthRateThrottle
from pydantic import field_validator

from .extraction import classify_input, extract_isbn, normalize_isbn
from .extractors import EXTRACTORS, recognize_url
from .models import CitationSource, CitationSourceLink
from .url_extraction import extract_url

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
    year: int | None = None
    isbn: str | None = None
    parent_id: int | None = None
    has_children: bool = False
    is_abstract: bool = False
    skip_locator: bool = False
    identifier_key: str = ""


class RecognitionChildSchema(Schema):
    id: int
    name: str
    skip_locator: bool = False


class RecognitionSchema(Schema):
    parent: CitationSourceParentSchema
    child: RecognitionChildSchema | None = None
    identifier: str | None = None


class SearchResponse(Schema):
    results: list[CitationSourceSearchSchema]
    recognition: RecognitionSchema | None = None


class CitationSourceCreateSchema(Schema):
    name: str
    source_type: str
    author: str = ""
    publisher: str = ""
    year: int | None = None
    month: int | None = None
    day: int | None = None
    date_note: str = ""
    isbn: str | None = None
    description: str = ""
    parent_id: int | None = None
    identifier: str = ""
    # Optional: atomically create a CitationSourceLink alongside the source.
    url: str | None = None
    link_label: str = ""
    link_type: str = "homepage"

    @field_validator("isbn", mode="before")
    @classmethod
    def coerce_empty_isbn_to_none(cls, v):
        """Empty string → None for nullable unique field."""
        return None if v == "" else v


class CitationSourceUpdateSchema(Schema):
    name: str | None = None
    source_type: str | None = None
    author: str | None = None
    publisher: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    date_note: str | None = None
    isbn: str | None = None
    description: str | None = None

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
    year: int | None = None
    isbn: str | None = None
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
    year: int | None = None
    month: int | None = None
    day: int | None = None
    date_note: str
    isbn: str | None = None
    description: str
    identifier_key: str = ""
    skip_locator: bool = False
    parent: CitationSourceParentSchema | None = None
    links: list[CitationSourceLinkSchema] = []
    children: list[CitationSourceChildSchema] = []
    created_at: str
    updated_at: str


class CitationSourceLinkCreateSchema(Schema):
    link_type: str
    url: str
    label: str = ""


class CitationSourceLinkUpdateSchema(Schema):
    link_type: str | None = None
    url: str | None = None
    label: str | None = None

    @field_validator("label", mode="before")
    @classmethod
    def coerce_null_to_empty(cls, v):
        return "" if v is None else v


class ExtractRequestSchema(Schema):
    input: str


class ExtractDraftSchema(Schema):
    name: str
    source_type: str
    author: str
    publisher: str
    year: int | None = None
    isbn: str | None = None
    url: str | None = None


class ExtractMatchSchema(Schema):
    id: int
    name: str
    skip_locator: bool = False


class ExtractResponseSchema(Schema):
    draft: ExtractDraftSchema | None = None
    match: ExtractMatchSchema | None = None
    error: str | None = None
    confidence: str = ""
    source_api: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_abstract(source_type, parent_id, has_children):
    """Source is abstract if it has children or is a root web/magazine source."""
    return has_children or (parent_id is None and source_type in ("web", "magazine"))


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
        raise HttpError(422, detail) from exc
    try:
        instance.save(update_fields=update_fields)
    except IntegrityError as exc:
        msg = str(exc).lower()
        if integrity_msg and ("unique" in msg or "duplicate" in msg):
            raise HttpError(422, integrity_msg) from exc
        raise HttpError(422, f"Integrity error: {exc}") from exc


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
        "skip_locator": source.skip_locator,
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
                "skip_locator": child.skip_locator,
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


def _is_url(q: str) -> bool:
    return q.startswith("http://") or q.startswith("https://")


def _build_recognition(rec) -> dict:
    """Serialize an extractors.Recognition into the API response shape."""
    result: dict = {
        "parent": {"id": rec.parent_id, "name": rec.parent_name},
        "child": None,
        "identifier": rec.identifier,
    }
    if rec.child_id is not None:
        result["child"] = {
            "id": rec.child_id,
            "name": rec.child_name,
            "skip_locator": rec.child_skip_locator,
        }
    return result


@citation_sources_router.get(
    "/search/",
    response=SearchResponse,
    auth=django_auth,
)
def search_citation_sources(request, q: str = ""):
    """Typeahead search with URL/ISBN recognition.

    Returns search results plus optional recognition metadata when the
    input is a recognized URL or ISBN.
    """
    q = q.strip()
    if not q:
        return {"results": [], "recognition": None}

    # --- Recognition (URL or ISBN) -----------------------------------------
    recognition = None
    if _is_url(q):
        rec = recognize_url(q)
        if rec is not None:
            recognition = _build_recognition(rec)

    # --- Text search -------------------------------------------------------
    text_filter = (
        Q(name__icontains=q)
        | Q(author__icontains=q)
        | Q(publisher__icontains=q)
        | Q(isbn__icontains=q)
        | Q(links__url__icontains=q)
    )
    # For ISBN-shaped input, also do exact match on normalized ISBN.
    if not _is_url(q):
        normalized_isbn = normalize_isbn(q)
        if normalized_isbn:
            text_filter = text_filter | Q(isbn=normalized_isbn)

    qs = (
        CitationSource.objects.filter(text_filter)
        .annotate(
            has_children=Exists(CitationSource.objects.filter(parent=OuterRef("pk")))
        )
        .distinct()
        .order_by("name")[:20]
    )
    results = [
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
            "skip_locator": s.skip_locator,
            "identifier_key": s.identifier_key,
        }
        for s in qs
    ]
    return {"results": results, "recognition": recognition}


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

    # When an identifier is provided and the parent has an extractor,
    # validate, normalize, and auto-build the child name and canonical URL.
    name = data.name
    url = data.url
    identifier = data.identifier
    if identifier and parent and parent.identifier_key:
        extractor = EXTRACTORS.get(parent.identifier_key)
        if extractor:
            normalized = extractor.normalize(identifier)
            if normalized is None:
                raise HttpError(
                    422,
                    f"Invalid identifier for {extractor.source_name}: {identifier!r}",
                )
            identifier = normalized
            if not name or name == data.identifier:
                name = f"{parent.name} #{identifier}"
            if not url:
                url = extractor.build_url(identifier)

    with transaction.atomic():
        source = CitationSource(
            name=name,
            source_type=data.source_type,
            author=data.author,
            publisher=data.publisher,
            year=data.year,
            month=data.month,
            day=data.day,
            date_note=data.date_note,
            isbn=data.isbn,
            description=data.description,
            identifier=identifier,
            parent=parent,
            created_by=request.user,
            updated_by=request.user,
        )
        _clean_and_save(
            source,
            integrity_msg="A source with this ISBN or identifier already exists.",
        )

        if url:
            link = CitationSourceLink(
                citation_source=source,
                link_type=data.link_type or "homepage",
                url=url,
                label=data.link_label,
                created_by=request.user,
                updated_by=request.user,
            )
            _clean_and_save(link)

    source = get_object_or_404(_detail_qs(), pk=source.pk)
    return Status(201, _serialize_detail(source))


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


class _ExtractThrottle(AuthRateThrottle):
    rate = "10/m"


@citation_sources_router.post(
    "/extract/",
    response=ExtractResponseSchema,
    auth=django_auth,
    throttle=[_ExtractThrottle("10/m")],
)
def extract_citation_source(request, data: ExtractRequestSchema):
    """Classify input and look up metadata from external APIs."""
    classified = classify_input(data.input)
    if classified is None:
        raise HttpError(422, "Unsupported input")

    kind, normalized = classified
    if kind == "isbn":
        result = extract_isbn(normalized)
    elif kind == "url":
        result = extract_url(normalized)
    else:
        raise HttpError(422, "Unsupported input")

    return ExtractResponseSchema(
        match=ExtractMatchSchema(**result.match) if result.match else None,
        draft=ExtractDraftSchema(**asdict(result.draft)) if result.draft else None,
        error=result.error,
        confidence=result.confidence,
        source_api=result.source_api,
    )


# ---------------------------------------------------------------------------
# Children / Detail / Links
# ---------------------------------------------------------------------------


@citation_sources_router.get(
    "/{source_id}/children/",
    response=list[CitationSourceChildSchema],
    auth=django_auth,
)
def list_citation_source_children(request, source_id: int, q: str = ""):
    """Filtered children of a source, searched by name, URL, identifier, or ISBN."""
    parent = get_object_or_404(CitationSource, pk=source_id)
    q = q.strip()
    if not q:
        return []
    children = (
        CitationSource.objects.filter(parent=parent)
        .filter(
            Q(name__icontains=q)
            | Q(links__url__icontains=q)
            | Q(identifier__icontains=q)
            | Q(isbn__icontains=q)
        )
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
            "skip_locator": child.skip_locator,
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
