"""Shared API schemas used by multiple routers."""

from __future__ import annotations

from typing import Any

from ninja import Schema
from pydantic import ConfigDict

from apps.provenance.schemas import EditCitationInput


class Ref(Schema):
    """A reference to a named entity with a slug."""

    name: str
    slug: str


class ErrorDetailSchema(Schema):
    """Plain 422 / 404 / 409 error body: just a ``detail`` string.

    The shared shape used for non-structured failures across catalog endpoints.
    Structured 422s (with ``field_errors`` / ``form_errors``) come from
    :class:`apps.catalog.api.edit_claims.StructuredValidationError` and have
    their own wire format; this schema covers the simpler "detail only" case.
    """

    detail: str


class ClaimPatchSchema(Schema):
    # ``fields`` maps claim-field name → new value. Values are polymorphic per
    # field (str, int, bool, slug string for FK-backed claims, None) and are
    # validated downstream by ``validate_claim_value``; no fixed TypedDict.
    fields: dict[str, Any]
    note: str = ""
    citation: EditCitationInput | None = None


class HierarchyClaimPatchSchema(Schema):
    # See ClaimPatchSchema.fields — polymorphic per claim field, validated downstream.
    fields: dict[str, Any] = {}
    parents: list[str] | None = None
    aliases: list[str] | None = None
    note: str = ""
    citation: EditCitationInput | None = None


class CorporateEntityClaimPatchSchema(Schema):
    # See ClaimPatchSchema.fields — polymorphic per claim field, validated downstream.
    fields: dict[str, Any] = {}
    aliases: list[str] | None = None
    note: str = ""
    citation: EditCitationInput | None = None


class GameplayFeatureInput(Schema):
    slug: str
    count: int | None = None


class CreditInput(Schema):
    person_slug: str
    role: str


class ModelClaimPatchSchema(Schema):
    # See ClaimPatchSchema.fields — polymorphic per claim field, validated downstream.
    fields: dict[str, Any] = {}
    themes: list[str] | None = None
    tags: list[str] | None = None
    reward_types: list[str] | None = None
    gameplay_features: list[GameplayFeatureInput] | None = None
    credits: list[CreditInput] | None = None
    abbreviations: list[str] | None = None
    note: str = ""
    citation: EditCitationInput | None = None


class ModelCreateSchema(Schema):
    name: str
    slug: str
    note: str = ""
    citation: EditCitationInput | None = None


class BlockingReferrerSchema(Schema):
    """An active reference blocking a soft-delete.

    Shared across all lifecycle-entity delete endpoints (Title, Model, …).
    The walker in :mod:`apps.catalog.api.soft_delete` produces these.
    """

    entity_type: str
    slug: str | None = None
    name: str
    relation: str
    blocked_target_type: str
    blocked_target_slug: str | None = None


class SoftDeleteBlockedSchema(Schema):
    """422 response from delete endpoints when active referrers block.

    ``blocked_by`` is empty (list, not null) when the block comes from an
    active-children count rather than PROTECT referrers — the frontend's
    delete-flow classifier relies on ``blocked_by`` being present as an array
    to recognise a blocked outcome. Required (no default) so that Pydantic
    union dispatch against :class:`AlreadyDeletedSchema` routes bare-``detail``
    bodies to the latter instead of filling an empty default here.
    """

    detail: str
    blocked_by: list[BlockingReferrerSchema]
    active_children_count: int = 0


class AlreadyDeletedSchema(Schema):
    """422 response from a delete endpoint when the entity is already soft-deleted.

    Paired with :class:`SoftDeleteBlockedSchema` / :class:`PersonSoftDeleteBlockedSchema`
    in a union on the 422 slot: ``blocked_by`` is absent here, so the frontend's
    delete-flow classifier falls through to ``form_error`` rather than ``blocked``.
    ``extra='forbid'`` forces Pydantic union dispatch to reject bodies carrying
    ``blocked_by`` and route them to the blocked-schema arm instead.
    """

    model_config = ConfigDict(extra="forbid")

    detail: str


class PersonSoftDeleteBlockedSchema(Schema):
    """422 response from Person delete when active credits block.

    Separate from :class:`SoftDeleteBlockedSchema` because Credits are
    referential, not lifecycle-owned children: the count is computed by
    joining Credit to its active parent Model/Series rather than walking an
    FK back from the child (see ``_active_credit_count`` in people.py).
    ``blocked_by`` is required for the same union-dispatch reason as
    :class:`SoftDeleteBlockedSchema`.
    """

    detail: str
    blocked_by: list[BlockingReferrerSchema]
    active_credit_count: int = 0


class ModelDeleteSchema(Schema):
    note: str = ""
    citation: EditCitationInput | None = None


class ModelRestoreSchema(Schema):
    note: str = ""
    citation: EditCitationInput | None = None


class ModelDeletePreviewSchema(Schema):
    model_name: str
    model_slug: str
    title_name: str
    title_slug: str
    changeset_count: int
    blocked_by: list[BlockingReferrerSchema] = []


class ModelDeleteResponseSchema(Schema):
    changeset_id: int
    affected_models: list[str]


class PersonCreateSchema(Schema):
    name: str
    slug: str
    note: str = ""
    citation: EditCitationInput | None = None


class PersonDeleteSchema(Schema):
    note: str = ""
    citation: EditCitationInput | None = None


class PersonRestoreSchema(Schema):
    note: str = ""
    citation: EditCitationInput | None = None


class PersonDeletePreviewSchema(Schema):
    person_name: str
    person_slug: str
    changeset_count: int
    # Count of Credits whose parent Model or Series is still active.
    # When non-zero the UI refuses the delete (see people.py:delete_person);
    # Credit rows are owned children of Model/Series so the generic
    # soft-delete walker doesn't see them.
    active_credit_count: int
    blocked_by: list[BlockingReferrerSchema] = []


class PersonDeleteResponseSchema(Schema):
    changeset_id: int
    affected_people: list[str]


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
    titles: list[EditOptionItem]
    models: list[EditOptionItem]


class ThemeSchema(Schema):
    name: str
    slug: str


class TitleMachineVariantSchema(Schema):
    """A variant of a machine model, shown nested under its parent."""

    name: str
    slug: str
    year: int | None = None
    thumbnail_url: str | None = None


class TitleMachineSchema(Schema):
    """A machine model shown in a list context (title detail, theme detail, etc.)."""

    name: str
    slug: str
    year: int | None = None
    manufacturer: Ref | None = None
    technology_generation_name: str | None = None
    thumbnail_url: str | None = None
    variants: list[TitleMachineVariantSchema] = []


class RelatedTitleSchema(Schema):
    """A title shown in a related-entity list context (manufacturer, system, etc.)."""

    name: str
    slug: str
    year: int | None = None
    manufacturer_name: str | None = None
    thumbnail_url: str | None = None


class TitleRefSchema(Schema):
    name: str
    slug: str
    abbreviations: list[str] = []
    model_count: int = 0
    manufacturer_name: str | None = None  # display-only, no paired slug
    year: int | None = None
    thumbnail_url: str | None = None


class SeriesRefSchema(Schema):
    name: str
    slug: str


class GameplayFeatureSchema(Schema):
    name: str
    slug: str
    count: int | None = None


class RewardTypeSchema(Schema):
    name: str
    slug: str


class FranchiseRefSchema(Schema):
    name: str
    slug: str


class CreditSchema(Schema):
    person: Ref
    role: str
    role_display: str
    role_sort_order: int


class CorporateEntityLocationAncestorRef(Schema):
    display_name: str
    location_path: str


class CorporateEntityLocationSchema(Schema):
    location_path: str
    location_type: str
    display_name: str
    slug: str
    ancestors: list[CorporateEntityLocationAncestorRef] = []
