"""Shared API schemas used by multiple routers."""

from __future__ import annotations

from typing import Any, Optional

from ninja import Schema


class ClaimSchema(Schema):
    source_name: Optional[str] = None
    source_slug: Optional[str] = None
    user_display: Optional[str] = None  # username for user-attributed claims
    field_name: str
    value: object
    citation: str
    created_at: str
    is_winner: bool


class ClaimPatchSchema(Schema):
    fields: dict[str, Any]


class ThemeSchema(Schema):
    name: str
    slug: str


class TitleMachineSchema(Schema):
    """A machine model shown in a list context (title detail, theme detail, etc.)."""

    name: str
    slug: str
    year: Optional[int] = None
    manufacturer_name: Optional[str] = None
    manufacturer_slug: Optional[str] = None
    technology_generation_name: Optional[str] = None
    thumbnail_url: Optional[str] = None


class RelatedTitleSchema(Schema):
    """A title shown in a related-entity list context (manufacturer, system, etc.)."""

    name: str
    slug: str
    year: Optional[int] = None
    manufacturer_name: Optional[str] = None
    thumbnail_url: Optional[str] = None


class SeriesRefSchema(Schema):
    name: str
    slug: str


class GameplayFeatureSchema(Schema):
    name: str
    slug: str


class FranchiseRefSchema(Schema):
    name: str
    slug: str
