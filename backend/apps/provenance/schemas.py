"""Shared API schemas for the provenance app.

These schemas are used by both the edit-history endpoints (api.py) and the
page-oriented changes endpoints (page_endpoints.py).
"""

from __future__ import annotations

from typing import Optional

from ninja import Schema


class FieldChangeSchema(Schema):
    """A single field change within a ChangeSet (old -> new)."""

    field_name: str
    claim_key: str
    old_value: Optional[object] = None
    new_value: object
    claim_id: Optional[int] = None
    claim_user_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_winning: Optional[bool] = None
    is_retracted: Optional[bool] = None


class RetractionSchema(Schema):
    claim_id: int
    field_name: str
    claim_key: str
    old_value: object


class ClaimSchema(Schema):
    """A single per-field claim as surfaced to the Sources UI."""

    source_name: Optional[str] = None
    source_slug: Optional[str] = None
    user_display: Optional[str] = None  # username for user-attributed claims
    field_name: str
    value: object
    citation: str
    created_at: str
    is_winner: bool
    changeset_note: Optional[str] = None


class EditCitationInput(Schema):
    """Reference an existing CitationInstance to clone onto a user edit."""

    citation_instance_id: int


class AttributionSchema(Schema):
    """License and source attribution for rendered content."""

    license_slug: Optional[str] = None
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    permissiveness_rank: Optional[int] = None
    requires_attribution: bool = False
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    attribution_text: Optional[str] = None


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
    year: Optional[int] = None
    locator: str
    links: list[InlineCitationLinkSchema] = []


class RichTextSchema(Schema):
    """A text field bundled with rendered HTML plus provenance metadata."""

    text: str = ""
    html: str = ""
    citations: list[InlineCitationSchema] = []
    attribution: Optional[AttributionSchema] = None
