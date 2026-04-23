"""Shared API schemas for the provenance app.

These schemas are used by both the edit-history endpoints (api.py) and the
page-oriented changes endpoints (page_endpoints.py).

Claim payloads are stored as JSON (``Claim.value`` is a ``JSONField``), so
``old_value`` / ``new_value`` / ``value`` fields are typed as ``object`` —
they carry scalars, dicts, lists, or null depending on the claim kind, and
the catalog-level schema is what actually constrains each field's shape.
"""

from __future__ import annotations

from ninja import Schema


class FieldChangeSchema(Schema):
    """A single field change within a ChangeSet (old -> new)."""

    field_name: str
    claim_key: str
    old_value: object | None = None
    new_value: object
    claim_id: int | None = None
    claim_user_id: int | None = None
    is_active: bool | None = None
    is_winning: bool | None = None
    is_retracted: bool | None = None


class RetractionSchema(Schema):
    claim_id: int
    field_name: str
    claim_key: str
    old_value: object


class ChangeSetSchema(Schema):
    """A grouped edit session with per-field diffs."""

    id: int
    user_display: str | None = None
    note: str
    created_at: str
    changes: list[FieldChangeSchema]
    retractions: list[RetractionSchema] = []


class ClaimSchema(Schema):
    """A single per-field claim as surfaced to the Sources UI."""

    source_name: str | None = None
    source_slug: str | None = None
    user_display: str | None = None  # username for user-attributed claims
    field_name: str
    value: object
    citation: str
    created_at: str
    is_winner: bool
    changeset_note: str | None = None


class EditCitationInput(Schema):
    """Reference an existing CitationInstance to clone onto a user edit."""

    citation_instance_id: int


class AttributionSchema(Schema):
    """License and source attribution for rendered content."""

    license_slug: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    permissiveness_rank: int | None = None
    requires_attribution: bool = False
    source_name: str | None = None
    source_url: str | None = None
    attribution_text: str | None = None


class ReviewLinkSchema(Schema):
    """A link out to an external page relevant to a needs-review item."""

    label: str
    url: str


class InlineCitationLinkSchema(Schema):
    """A link attached to a citation source."""

    url: str
    label: str


class InlineCitationSchema(Schema):
    """Metadata for an inline citation in rendered markdown."""

    id: int
    index: int
    source_name: str
    source_type: str
    author: str
    year: int | None = None
    locator: str
    links: list[InlineCitationLinkSchema] = []


class RichTextSchema(Schema):
    """A text field bundled with rendered HTML plus provenance metadata."""

    text: str = ""
    html: str = ""
    citations: list[InlineCitationSchema] = []
    attribution: AttributionSchema | None = None
