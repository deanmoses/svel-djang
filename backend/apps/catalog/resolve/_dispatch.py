"""Centralised resolution dispatch after claim mutations.

Provides :func:`resolve_after_mutation` — a single entry-point that any
module (including provenance) can call after mutating claims on an entity.
Internally it routes to the correct resolver(s) based on entity type and
the claim field names that changed, then invalidates cached endpoint data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

from .._alias_registry import discover_alias_types
from ..cache import invalidate_all

if TYPE_CHECKING:
    from django.db import models

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dispatch tables — built lazily to avoid import-time model access
# ---------------------------------------------------------------------------

_alias_dispatch: dict[str, type] | None = None


def _get_alias_dispatch() -> dict[str, type]:
    """field_name → parent model class for alias resolvers."""
    global _alias_dispatch  # noqa: PLW0603
    if _alias_dispatch is None:
        _alias_dispatch = {
            field_name: model for model, field_name in discover_alias_types()
        }
    return _alias_dispatch


_parent_dispatch: dict[str, tuple[type, str | None]] | None = None


def _get_parent_dispatch() -> dict[str, tuple[type, str | None]]:
    """field_name → (model, claim_field_prefix) for _resolve_parents()."""
    global _parent_dispatch  # noqa: PLW0603
    if _parent_dispatch is None:
        from ..models import GameplayFeature, Theme

        _parent_dispatch = {
            "theme_parent": (Theme, None),
            "gameplay_feature_parent": (GameplayFeature, "gameplay_feature"),
        }
    return _parent_dispatch


_custom_dispatch: dict[str, tuple[type, str, str]] | None = None


def _get_custom_dispatch() -> dict[str, tuple[type, str, str]]:
    """field_name → (entity_model, resolver_function_name, id_kwarg_name).

    Each entry specifies which model type it applies to, which
    ``resolve_all_*`` function to call, and which keyword argument
    receives the scoped ID set.
    """
    global _custom_dispatch  # noqa: PLW0603
    if _custom_dispatch is None:
        from ..models import CorporateEntity, Title

        _custom_dispatch = {
            "abbreviation": (Title, "resolve_all_title_abbreviations", "model_ids"),
            "location": (
                CorporateEntity,
                "resolve_all_corporate_entity_locations",
                "entity_ids",
            ),
        }
    return _custom_dispatch


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_after_mutation(
    entity: models.Model,
    field_names: list[str] | None = None,
) -> None:
    """Re-resolve an entity after its claims have been mutated.

    Call this inside a ``transaction.atomic()`` block after creating,
    deactivating, or modifying claims.  Resolution runs synchronously
    inside the caller's transaction.  Cache invalidation runs after
    resolution completes.

    Parameters
    ----------
    entity:
        The catalog entity whose claims changed.
    field_names:
        The claim ``field_name`` values that were mutated.  When ``None``,
        all applicable resolvers run (safe but less efficient).
    """
    from ..models import MachineModel

    if isinstance(entity, MachineModel):
        _resolve_machine_model(entity)
    else:
        _resolve_non_machine_model(entity, field_names)

    transaction.on_commit(invalidate_all)


# ---------------------------------------------------------------------------
# Internal routing
# ---------------------------------------------------------------------------


def _resolve_machine_model(entity: models.Model) -> None:
    """MachineModel path — resolve_model() handles everything."""
    from . import resolve_model

    resolve_model(entity)


def _resolve_non_machine_model(
    entity: models.Model,
    field_names: list[str] | None,
) -> None:
    """Non-MachineModel path — dispatch relationship resolvers then scalars."""
    from ..claims import get_relationship_namespaces
    from ._entities import resolve_entity
    from ._media import resolve_media_attachments
    from ._relationships import _resolve_aliases, _resolve_parents

    relationship_ns = get_relationship_namespaces()
    entity_type = type(entity)

    if field_names is not None:
        rel_fields = [fn for fn in field_names if fn in relationship_ns]
    else:
        rel_fields = None  # signals "run all applicable"

    # --- Alias resolvers ---
    alias_dispatch = _get_alias_dispatch()
    if rel_fields is not None:
        for fn in rel_fields:
            if fn in alias_dispatch and alias_dispatch[fn] is entity_type:
                _resolve_aliases(alias_dispatch[fn], fn)
    else:
        for fn, parent_model in alias_dispatch.items():
            if parent_model is entity_type:
                _resolve_aliases(parent_model, fn)

    # --- Parent hierarchy resolvers ---
    parent_dispatch = _get_parent_dispatch()
    if rel_fields is not None:
        for fn in rel_fields:
            if fn in parent_dispatch:
                model, prefix = parent_dispatch[fn]
                if model is entity_type:
                    _resolve_parents(model, claim_field_prefix=prefix)
    else:
        for _fn, (model, prefix) in parent_dispatch.items():
            if model is entity_type:
                _resolve_parents(model, claim_field_prefix=prefix)

    # --- Custom resolvers (abbreviation, location) ---
    custom_dispatch = _get_custom_dispatch()
    if rel_fields is not None:
        for fn in rel_fields:
            if fn in custom_dispatch and custom_dispatch[fn][0] is entity_type:
                _call_custom_resolver(custom_dispatch[fn], entity.pk)
    else:
        for _fn, spec in custom_dispatch.items():
            if spec[0] is entity_type:
                _call_custom_resolver(spec, entity.pk)

    # --- Media attachments ---
    from apps.core.models import MediaSupported

    if isinstance(entity, MediaSupported):
        if rel_fields is None or "media_attachment" in rel_fields:
            from django.contrib.contenttypes.models import ContentType

            ct = ContentType.objects.get_for_model(entity_type)
            resolve_media_attachments(content_type_id=ct.id, entity_ids={entity.pk})

    # --- Scalar fields ---
    resolve_entity(entity)


def _call_custom_resolver(spec: tuple[type, str, str], entity_pk: int) -> None:
    """Call a custom resolver by name with scoped IDs."""
    from . import _relationships

    _model, func_name, id_kwarg = spec
    func = getattr(_relationships, func_name)
    func(**{id_kwarg: {entity_pk}})
