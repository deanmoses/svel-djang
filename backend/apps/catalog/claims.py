"""Catalog-level helpers for relationship claims.

Domain knowledge about relationship claim types lives here, keeping the
provenance layer fully generic.  Ingestion commands and the resolution layer
import from this module rather than constructing claim_keys directly.
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.provenance.models import make_claim_key

# ---------------------------------------------------------------------------
# Relationship schema registry
# ---------------------------------------------------------------------------
# Maps namespace → {value_key: identity_key}.
#   value_key  – key in the claim value dict (e.g., "person_slug")
#   identity_key – key used in the claim_key string (e.g., "person")

RELATIONSHIP_SCHEMAS: dict[str, dict[str, str]] = {
    "credit": {"person_slug": "person", "role": "role"},
    "theme": {"theme_slug": "theme"},
    "tag": {"tag_slug": "tag"},
    "gameplay_feature": {"gameplay_feature_slug": "gameplay_feature"},
}

RELATIONSHIP_NAMESPACES = frozenset(RELATIONSHIP_SCHEMAS)


# ---------------------------------------------------------------------------
# Claim construction helpers
# ---------------------------------------------------------------------------


def build_relationship_claim(
    field_name: str,
    identity: dict,
    exists: bool = True,
) -> tuple[str, dict]:
    """Return ``(claim_key, value)`` for a relationship claim.

    ``identity`` contains the identity fields for this relationship, e.g.,
    ``{"person_slug": "pat-lawlor", "role": "art"}``.

    The claim_key is derived from identity using the schema for *field_name*.
    The value dict includes identity fields plus ``exists``.
    """
    schema = RELATIONSHIP_SCHEMAS.get(field_name)
    if schema is None:
        raise ValueError(f"Unknown relationship namespace: {field_name!r}")

    identity_parts = {}
    for value_key, identity_key in sorted(schema.items()):
        if value_key not in identity:
            raise ValueError(f"Missing required key {value_key!r} for {field_name!r}")
        identity_parts[identity_key] = identity[value_key]

    claim_key = make_claim_key(field_name, **identity_parts)
    value = {**identity, "exists": exists}
    return claim_key, value


def make_authoritative_scope(
    model_class: type[models.Model],
    object_ids,
) -> set[tuple[int, int]]:
    """Build an authoritative_scope set from a model class and object IDs.

    Convenience wrapper for the common single-content-type case used by
    ingest commands.
    """
    ct_id = ContentType.objects.get_for_model(model_class).pk
    return {(ct_id, obj_id) for obj_id in object_ids}
