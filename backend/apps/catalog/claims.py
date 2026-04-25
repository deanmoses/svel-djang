"""Catalog-level helpers for relationship claims.

Domain knowledge about relationship claim shapes lives here via
``register_catalog_relationship_schemas()``, called from
``CatalogConfig.ready()``. The unified registry is owned by
``apps.provenance.validation``; this module only declares catalog
namespaces and provides the ``build_relationship_claim`` helper that
ingest commands and the resolution layer use.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.types import JsonBody
from apps.provenance.models import IdentityPart, make_claim_key
from apps.provenance.validation import (
    RelationshipSchema,
    ValueKeySpec,
    get_all_relationship_schemas,
    get_relationship_schema,
    register_relationship_schema,
)
from apps.provenance.validation import (
    get_relationship_namespaces as _get_relationship_namespaces,
)

# A (claim_key, value_dict) pair ready to write as a relationship Claim row.
# claim_key is the canonical compound string; value_dict is the JSONField
# payload — identity fields plus "exists", optionally "category"/"is_primary".
RelationshipClaim = tuple[str, JsonBody]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_catalog_relationship_schemas() -> None:
    """Register every catalog relationship namespace. Called from ``ready()``.

    Each namespace is declared exactly once with its value-keys and the set
    of subject models it applies to.
    """
    from apps.catalog.models import (
        CorporateEntity,
        CreditRole,
        GameplayFeature,
        Location,
        MachineModel,
        Person,
        RewardType,
        Series,
        Tag,
        Theme,
        Title,
    )
    from apps.media.models import MediaAsset, MediaSupported

    from ._alias_registry import discover_alias_types

    # Credit: Person + CreditRole on MachineModel and Series.
    register_relationship_schema(
        namespace="credit",
        value_keys=(
            ValueKeySpec(
                name="person",
                scalar_type=int,
                required=True,
                identity="person",
                fk_target=(Person, "pk"),
            ),
            ValueKeySpec(
                name="role",
                scalar_type=int,
                required=True,
                identity="role",
                fk_target=(CreditRole, "pk"),
            ),
        ),
        valid_subjects=frozenset({MachineModel, Series}),
    )

    # Gameplay feature M2M on MachineModel — with optional integer count.
    register_relationship_schema(
        namespace="gameplay_feature",
        value_keys=(
            ValueKeySpec(
                name="gameplay_feature",
                scalar_type=int,
                required=True,
                identity="gameplay_feature",
                fk_target=(GameplayFeature, "pk"),
            ),
            ValueKeySpec(
                name="count",
                scalar_type=int,
                required=False,
                nullable=True,
            ),
        ),
        valid_subjects=frozenset({MachineModel}),
    )

    # Simple M2Ms on MachineModel — theme / tag / reward_type.
    register_relationship_schema(
        namespace="theme",
        value_keys=(
            ValueKeySpec(
                name="theme",
                scalar_type=int,
                required=True,
                identity="theme",
                fk_target=(Theme, "pk"),
            ),
        ),
        valid_subjects=frozenset({MachineModel}),
    )
    register_relationship_schema(
        namespace="tag",
        value_keys=(
            ValueKeySpec(
                name="tag",
                scalar_type=int,
                required=True,
                identity="tag",
                fk_target=(Tag, "pk"),
            ),
        ),
        valid_subjects=frozenset({MachineModel}),
    )
    register_relationship_schema(
        namespace="reward_type",
        value_keys=(
            ValueKeySpec(
                name="reward_type",
                scalar_type=int,
                required=True,
                identity="reward_type",
                fk_target=(RewardType, "pk"),
            ),
        ),
        valid_subjects=frozenset({MachineModel}),
    )

    # Abbreviation (literal) on Title + MachineModel.
    register_relationship_schema(
        namespace="abbreviation",
        value_keys=(
            ValueKeySpec(
                name="value",
                scalar_type=str,
                required=True,
                identity="value",
            ),
        ),
        valid_subjects=frozenset({Title, MachineModel}),
    )

    # Location on CorporateEntity.
    register_relationship_schema(
        namespace="location",
        value_keys=(
            ValueKeySpec(
                name="location",
                scalar_type=int,
                required=True,
                identity="location",
                fk_target=(Location, "pk"),
            ),
        ),
        valid_subjects=frozenset({CorporateEntity}),
    )

    # Hierarchy parents (self-referential).
    register_relationship_schema(
        namespace="theme_parent",
        value_keys=(
            ValueKeySpec(
                name="parent",
                scalar_type=int,
                required=True,
                identity="parent",
                fk_target=(Theme, "pk"),
            ),
        ),
        valid_subjects=frozenset({Theme}),
    )
    register_relationship_schema(
        namespace="gameplay_feature_parent",
        value_keys=(
            ValueKeySpec(
                name="parent",
                scalar_type=int,
                required=True,
                identity="parent",
                fk_target=(GameplayFeature, "pk"),
            ),
        ),
        valid_subjects=frozenset({GameplayFeature}),
    )

    # Alias namespaces — one schema per AliasBase subclass.
    for alias_type in discover_alias_types():
        register_relationship_schema(
            namespace=alias_type.claim_field,
            value_keys=(
                ValueKeySpec(
                    name="alias_value",
                    scalar_type=str,
                    required=True,
                    identity="alias",
                ),
                ValueKeySpec(
                    name="alias_display",
                    scalar_type=str,
                    required=False,
                ),
            ),
            valid_subjects=frozenset({alias_type.parent_model}),
        )

    # Media attachment — derived at registration by walking all concrete
    # ``MediaSupported`` subclasses. ``apps.get_models()`` handles transitive
    # subclasses that ``__subclasses__()`` would miss if an intermediate
    # abstract base is ever introduced.
    from django.apps import apps as _apps

    media_subjects = frozenset(
        m
        for m in _apps.get_models()
        if issubclass(m, MediaSupported) and not m._meta.abstract
    )
    register_relationship_schema(
        namespace="media_attachment",
        value_keys=(
            ValueKeySpec(
                name="media_asset",
                scalar_type=int,
                required=True,
                identity="media_asset",
                fk_target=(MediaAsset, "pk"),
            ),
            ValueKeySpec(
                name="category",
                scalar_type=str,
                required=False,
                nullable=True,
            ),
            ValueKeySpec(
                name="is_primary",
                scalar_type=bool,
                required=False,
            ),
        ),
        valid_subjects=media_subjects,
    )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_relationship_namespaces() -> frozenset[str]:
    """Return the full set of registered relationship namespace names.

    Thin re-export of the cached provenance-layer function, kept at this
    module path for existing import sites.
    """
    return _get_relationship_namespaces()


def get_all_namespace_keys() -> dict[str, list[str]]:
    """Return namespace → list of identity value-key names for every namespace.

    Used by tests to verify that every namespace classifies correctly.
    """
    result: dict[str, list[str]] = {}
    for namespace, schema in get_all_relationship_schemas().items():
        result[namespace] = [
            spec.name for spec in schema.value_keys if spec.identity is not None
        ]
    return result


def build_relationship_claim(
    field_name: str,
    identity: Mapping[str, IdentityPart],
    exists: bool = True,
) -> RelationshipClaim:
    """Return ``(claim_key, value)`` for a relationship claim.

    ``identity`` contains the identity fields for this relationship, e.g.,
    ``{"person": 42, "role": 5}`` or ``{"alias_value": "foo"}``. Keys are
    value-dict names (``alias_value``), not identity labels (``alias``) —
    the mapping is resolved via ``ValueKeySpec.identity``.

    The claim_key is derived from identity using the registered schema for
    *field_name*. The value dict includes all identity fields plus ``exists``.
    """
    schema = get_relationship_schema(field_name)
    if schema is None:
        raise ValueError(f"Unknown relationship namespace: {field_name!r}")

    identity_parts: dict[str, IdentityPart] = {}
    for spec in schema.value_keys:
        if spec.identity is None:
            continue
        if spec.name not in identity:
            raise ValueError(f"Missing required key {spec.name!r} for {field_name!r}")
        identity_parts[spec.identity] = identity[spec.name]
    claim_key = make_claim_key(field_name, **identity_parts)
    value: JsonBody = {**identity, "exists": exists}
    return claim_key, value


def build_media_attachment_claim(
    entity: models.Model,
    asset_pk: int,
    *,
    category: str | None = None,
    is_primary: bool = False,
    exists: bool = True,
) -> RelationshipClaim:
    """Return ``(claim_key, value)`` for a ``media_attachment`` claim.

    Validates *category* against the entity's ``MEDIA_CATEGORIES`` before
    building the claim.  Raises ``ValueError`` for invalid categories.
    All code paths that create ``media_attachment`` claims should use this
    helper so that category validation happens exactly once.
    """
    from apps.media.models import MediaSupported

    model_class = type(entity)
    if not issubclass(model_class, MediaSupported):
        raise ValueError(f"{model_class.__name__} does not support media attachments.")

    allowed = model_class.MEDIA_CATEGORIES
    if category is not None:
        if not allowed:
            raise ValueError(f"No media categories defined for {model_class.__name__}.")
        if category not in allowed:
            raise ValueError(
                f"Invalid category {category!r} for {model_class.__name__}. "
                f"Allowed: {', '.join(allowed)}."
            )

    claim_key, value = build_relationship_claim(
        "media_attachment",
        {"media_asset": asset_pk},
        exists=exists,
    )
    value["category"] = category
    value["is_primary"] = is_primary
    return claim_key, value


def make_authoritative_scope(
    model_class: type[models.Model],
    object_ids: Iterable[int],
) -> set[tuple[int, int]]:
    """Build an authoritative_scope set from a model class and object IDs.

    Convenience wrapper for the common single-content-type case used by
    ingest commands.
    """
    ct_id = ContentType.objects.get_for_model(model_class).pk
    return {(ct_id, obj_id) for obj_id in object_ids}


# Public surface. ``RelationshipSchema`` / ``ValueKeySpec`` are re-exported
# because this module instantiates them; downstream code should import from
# whichever module they already use.
__all__ = [
    "RelationshipClaim",
    "RelationshipSchema",
    "ValueKeySpec",
    "build_media_attachment_claim",
    "build_relationship_claim",
    "get_all_namespace_keys",
    "get_relationship_namespaces",
    "make_authoritative_scope",
    "register_catalog_relationship_schemas",
]
