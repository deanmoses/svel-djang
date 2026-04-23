"""Catalog-level helpers for relationship claims.

Domain knowledge about relationship claim types lives here, keeping the
provenance layer fully generic.  Ingestion commands and the resolution layer
import from this module rather than constructing claim_keys directly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import NamedTuple

from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.types import JsonBody
from apps.provenance.models import IdentityPart, make_claim_key

# A (claim_key, value_dict) pair ready to write as a relationship Claim row.
# claim_key is the canonical compound string; value_dict is the JSONField
# payload — identity fields plus "exists", optionally "category"/"is_primary".
RelationshipClaim = tuple[str, JsonBody]

# ---------------------------------------------------------------------------
# Relationship schema registry
# ---------------------------------------------------------------------------
# Two kinds of relationship namespace:
#
# Entity-reference — value dict keys are PKs referencing target models.
#   ENTITY_REF_TARGETS is the single source of truth: schema keys,
#   validation target registration, and RELATIONSHIP_NAMESPACES are all
#   derived from it.
#
# Literal-value — value dict keys store literal strings (aliases,
#   abbreviations) where value_key differs from identity_key.


class RefKey(NamedTuple):
    """An entity-reference key in a relationship claim value dict."""

    name: str  # key in both value dict and claim_key ("person", "theme")
    model: type[models.Model]  # target model for PK validation


class LiteralKey(NamedTuple):
    """A literal-value key where the value dict key differs from the claim_key key."""

    value_key: str  # key in claim value dict ("alias_value")
    identity_key: str  # key in claim_key string ("alias")


def _build_entity_ref_targets() -> dict[str, list[RefKey]]:
    """Deferred import to avoid circular dependency at module load."""
    from apps.catalog.models import (
        CreditRole,
        GameplayFeature,
        Location,
        Person,
        RewardType,
        Tag,
        Theme,
    )
    from apps.media.models import MediaAsset

    return {
        "credit": [RefKey("person", Person), RefKey("role", CreditRole)],
        "theme": [RefKey("theme", Theme)],
        "tag": [RefKey("tag", Tag)],
        "gameplay_feature": [RefKey("gameplay_feature", GameplayFeature)],
        "reward_type": [RefKey("reward_type", RewardType)],
        "location": [RefKey("location", Location)],
        "theme_parent": [RefKey("parent", Theme)],
        "gameplay_feature_parent": [RefKey("parent", GameplayFeature)],
        "media_attachment": [RefKey("media_asset", MediaAsset)],
    }


# Populated lazily by _get_entity_ref_targets().
_entity_ref_targets: dict[str, list[RefKey]] | None = None


def _get_entity_ref_targets() -> dict[str, list[RefKey]]:
    global _entity_ref_targets
    if _entity_ref_targets is None:
        _entity_ref_targets = _build_entity_ref_targets()
    return _entity_ref_targets


_literal_schemas: dict[str, LiteralKey] | None = None


def _get_literal_schemas() -> dict[str, LiteralKey]:
    """Return literal namespace schemas, auto-discovering alias types.

    Lazy — safe to call at any time; caches after first call.
    Follows the same pattern as ``_get_entity_ref_targets()``.
    """
    global _literal_schemas
    if _literal_schemas is None:
        from ._alias_registry import discover_alias_types

        _literal_schemas = {"abbreviation": LiteralKey("value", "value")}
        for at in discover_alias_types():
            _literal_schemas[at.claim_field] = LiteralKey("alias_value", "alias")
    return _literal_schemas


_relationship_namespaces: frozenset[str] | None = None


def get_relationship_namespaces() -> frozenset[str]:
    """Return the full set of relationship namespace names.

    Lazy — safe to call at any time; caches after first call.
    """
    global _relationship_namespaces
    if _relationship_namespaces is None:
        _relationship_namespaces = frozenset(_get_entity_ref_targets()) | frozenset(
            _get_literal_schemas()
        )
    return _relationship_namespaces


def register_relationship_targets() -> None:
    """Push catalog target-model knowledge into the provenance registry.

    Called once from ``CatalogConfig.ready()``.  Derived from
    ``ENTITY_REF_TARGETS`` — no hand-maintained second dict.
    """
    from apps.provenance.validation import register_relationship_targets as _register

    _register(
        {
            namespace: [(rk.name, rk.model, "pk") for rk in ref_keys]
            for namespace, ref_keys in _get_entity_ref_targets().items()
        }
    )


# ---------------------------------------------------------------------------
# Claim construction helpers
# ---------------------------------------------------------------------------


def get_all_namespace_keys() -> dict[str, list[str]]:
    """Return namespace → list of identity key names for every relationship namespace.

    Used by tests to verify that every namespace classifies correctly.
    """
    result: dict[str, list[str]] = {}
    for ns, ref_keys in _get_entity_ref_targets().items():
        result[ns] = [rk.name for rk in ref_keys]
    for ns, lit in _get_literal_schemas().items():
        result[ns] = [lit.value_key]
    return result


def build_relationship_claim(
    field_name: str,
    identity: Mapping[str, IdentityPart],
    exists: bool = True,
) -> RelationshipClaim:
    """Return ``(claim_key, value)`` for a relationship claim.

    ``identity`` contains the identity fields for this relationship, e.g.,
    ``{"person": 42, "role": 5}``.

    The claim_key is derived from identity using the registry for *field_name*.
    The value dict includes identity fields plus ``exists``.
    """
    entity_refs = _get_entity_ref_targets()
    ref_keys = entity_refs.get(field_name)
    if ref_keys is not None:
        # Entity-reference namespace: key names are identity keys.
        expected = sorted(rk.name for rk in ref_keys)
        for key in expected:
            if key not in identity:
                raise ValueError(f"Missing required key {key!r} for {field_name!r}")
        identity_parts = {k: identity[k] for k in expected}
    else:
        literal = _get_literal_schemas().get(field_name)
        if literal is None:
            raise ValueError(f"Unknown relationship namespace: {field_name!r}")
        # Literal namespace: map value_key → identity_key.
        if literal.value_key not in identity:
            raise ValueError(
                f"Missing required key {literal.value_key!r} for {field_name!r}"
            )
        identity_parts = {literal.identity_key: identity[literal.value_key]}

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
    from apps.core.models import MediaSupported

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
