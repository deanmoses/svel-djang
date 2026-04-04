"""Shared API schemas used by multiple routers."""

from __future__ import annotations

from typing import Any, Optional

from ninja import Schema


class Ref(Schema):
    """A reference to a named entity with a slug."""

    name: str
    slug: str


class ClaimSchema(Schema):
    source_name: Optional[str] = None
    source_slug: Optional[str] = None
    user_display: Optional[str] = None  # username for user-attributed claims
    field_name: str
    value: object
    citation: str
    created_at: str
    is_winner: bool
    changeset_note: Optional[str] = None


class ClaimPatchSchema(Schema):
    fields: dict[str, Any]


class HierarchyClaimPatchSchema(Schema):
    fields: dict[str, Any] = {}
    parents: list[str] | None = None
    aliases: list[str] | None = None
    note: str = ""


class CorporateEntityClaimPatchSchema(Schema):
    fields: dict[str, Any] = {}
    aliases: list[str] | None = None
    note: str = ""


class GameplayFeatureInput(Schema):
    slug: str
    count: int | None = None


class CreditInput(Schema):
    person_slug: str
    role: str


class ModelClaimPatchSchema(Schema):
    fields: dict[str, Any] = {}
    themes: list[str] | None = None
    tags: list[str] | None = None
    reward_types: list[str] | None = None
    gameplay_features: list[GameplayFeatureInput] | None = None
    credits: list[CreditInput] | None = None
    abbreviations: list[str] | None = None
    note: str = ""


class EditOptionItem(Schema):
    slug: str
    label: str


class ModelEditOptionsSchema(Schema):
    themes: list[EditOptionItem]
    tags: list[EditOptionItem]
    reward_types: list[EditOptionItem]
    gameplay_features: list[EditOptionItem]
    technology_generations: list[EditOptionItem]
    technology_subgenerations: list[EditOptionItem]
    display_types: list[EditOptionItem]
    display_subtypes: list[EditOptionItem]
    cabinets: list[EditOptionItem]
    game_formats: list[EditOptionItem]
    systems: list[EditOptionItem]
    corporate_entities: list[EditOptionItem]
    people: list[EditOptionItem]
    credit_roles: list[EditOptionItem]
    models: list[EditOptionItem]


class AttributionSchema(Schema):
    """License and attribution info for a piece of content (image, description, etc.)."""

    license_slug: Optional[str] = None
    license_name: Optional[str] = None
    license_url: Optional[str] = None
    permissiveness_rank: Optional[int] = None
    requires_attribution: bool = False
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    attribution_text: Optional[str] = None


class RichTextSchema(Schema):
    """A text field bundled with its rendered HTML and attribution."""

    text: str = ""
    html: str = ""
    attribution: Optional[AttributionSchema] = None


class ThemeSchema(Schema):
    name: str
    slug: str


class TitleMachineVariantSchema(Schema):
    """A variant of a machine model, shown nested under its parent."""

    name: str
    slug: str
    year: Optional[int] = None
    thumbnail_url: Optional[str] = None


class TitleMachineSchema(Schema):
    """A machine model shown in a list context (title detail, theme detail, etc.)."""

    name: str
    slug: str
    year: Optional[int] = None
    manufacturer: Optional[Ref] = None
    technology_generation_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    variants: list[TitleMachineVariantSchema] = []


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
    count: Optional[int] = None


class RewardTypeSchema(Schema):
    name: str
    slug: str


class FieldChangeSchema(Schema):
    """A single field change within a ChangeSet (old → new)."""

    field_name: str
    claim_key: str
    old_value: Optional[object] = None
    new_value: object


class ChangeSetSchema(Schema):
    """A grouped edit session with per-field diffs."""

    id: int
    user_display: Optional[str] = None
    note: str
    created_at: str
    changes: list[FieldChangeSchema]


class FranchiseRefSchema(Schema):
    name: str
    slug: str


class MediaRenditionsSchema(Schema):
    thumb: str
    display: str


class UploadedMediaSchema(Schema):
    asset_uuid: str
    category: Optional[str] = None
    is_primary: bool
    renditions: MediaRenditionsSchema
