"""Alias-type discovery from AliasBase subclasses.

Shared module that both ``claims.py`` and ``resolve/`` can import without
creating circular dependencies — it only touches ``core.models.AliasBase``.
"""

from __future__ import annotations

import functools
from typing import NamedTuple

from django.apps import apps
from django.db import models


class AliasType(NamedTuple):
    """A discovered ``AliasBase`` subclass and the claim field that holds its aliases."""

    parent_model: type[models.Model]
    claim_field: str


@functools.lru_cache(maxsize=1)
def discover_alias_types() -> tuple[AliasType, ...]:
    """Return an ``AliasType`` per ``AliasBase`` subclass.

    Must be called after Django's models are loaded. The
    ``@functools.lru_cache(maxsize=1)`` decorator pins the first result,
    so this is both a discovery walk and a process-lifetime cache.

    Subclasses are guaranteed to declare ``alias_claim_field`` by
    ``AliasBase.__init_subclass__`` — the validation lives at class
    creation, not here.
    """
    apps.check_models_ready()

    from apps.core.models import AliasBase

    result: list[AliasType] = []
    for alias_cls in AliasBase.__subclasses__():
        # Each AliasBase subclass has exactly one FK to its parent model.
        fks = [
            f
            for f in alias_cls._meta.get_fields()
            if hasattr(f, "related_model") and f.many_to_one
        ]
        if len(fks) != 1:
            raise RuntimeError(
                f"{alias_cls.__name__} has {len(fks)} ForeignKeys; expected exactly 1"
            )
        parent_model = fks[0].related_model
        if parent_model is None or isinstance(parent_model, str):
            raise RuntimeError(f"{alias_cls.__name__} FK has no related model")
        result.append(AliasType(parent_model, alias_cls.alias_claim_field))

    return tuple(sorted(result, key=lambda at: at.claim_field))
