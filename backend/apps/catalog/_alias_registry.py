"""Alias-type discovery from AliasBase subclasses.

Shared module that both ``claims.py`` and ``resolve/`` can import without
creating circular dependencies — it only touches ``core.models.AliasBase``.
"""

from __future__ import annotations

import functools

from django.db import models


@functools.lru_cache(maxsize=1)
def discover_alias_types() -> tuple[tuple[type[models.Model], str], ...]:
    """Return ``((parent_model, claim_field_name), ...)`` for every AliasBase subclass.

    Must be called after Django's app registry is ready (i.e. not at import
    time).  Results are cached after the first call.
    """
    from apps.core.models import AliasBase

    result: list[tuple[type[models.Model], str]] = []
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
        verbose_name = parent_model._meta.verbose_name
        if verbose_name is None:
            raise RuntimeError(f"{alias_cls.__name__} parent model has no verbose_name")
        claim_field = f"{verbose_name.replace(' ', '_')}_alias"
        result.append((parent_model, claim_field))

    return tuple(sorted(result, key=lambda pair: pair[1]))
