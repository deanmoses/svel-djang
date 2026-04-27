"""System checks for ``LinkableModel`` subclass declarations.

Verified at ``manage.py check`` (and at server boot) — never at first
request — so a missing or malformed contract crashes early.

Each concrete ``LinkableModel`` subclass must:

- declare non-empty ``entity_type`` and ``entity_type_plural`` strings
  (already validated in ``__init_subclass__``);
- have unique ``entity_type`` and ``entity_type_plural`` values across all
  subclasses;
- declare a ``public_id_field`` that resolves to a real concrete model
  field (or the inherited default, ``"slug"``) with ``unique=True``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.apps.config import AppConfig
from django.core.checks import CheckMessage, Error, Tags, register
from django.core.exceptions import FieldDoesNotExist

from apps.core.models import LinkableModel


@register(Tags.models)
def check_linkable_models(
    app_configs: Sequence[AppConfig] | None,
    # ``**kwargs`` is required by Django's check-framework signature and may
    # carry forward-compatible options (e.g. ``databases``); we don't read
    # any of them, so ``Any`` is the documented type.
    **kwargs: Any,  # noqa: ANN401
) -> list[CheckMessage]:
    """Validate every concrete ``LinkableModel`` subclass."""
    _ = app_configs, kwargs
    errors: list[CheckMessage] = []
    seen_entity_type: dict[str, type] = {}
    seen_entity_type_plural: dict[str, type] = {}

    def walk(cls: type[LinkableModel]) -> None:
        for subclass in cls.__subclasses__():
            walk(subclass)
            meta = getattr(subclass, "_meta", None)
            if meta is None or meta.abstract:
                continue
            errors.extend(
                _check_one(subclass, seen_entity_type, seen_entity_type_plural)
            )

    # ``LinkableModel`` is abstract; mypy's ``type-abstract`` check flags
    # passing it where a concrete ``type[LinkableModel]`` is expected, but
    # ``__subclasses__()`` is the documented walk entry point.
    walk(LinkableModel)  # type: ignore[type-abstract]
    return errors


def _check_one(
    model: type,
    seen_entity_type: dict[str, type],
    seen_entity_type_plural: dict[str, type],
) -> list[CheckMessage]:
    # ``model`` is typed as ``type`` (not ``type[LinkableModel]``) because the
    # body is fully duck-typed via ``getattr`` and ``model._meta.get_field``.
    # Production callers always pass a ``type[LinkableModel]`` from
    # ``LinkableModel.__subclasses__()``; tests pass synthetic stand-ins to
    # exercise individual error branches without registering real Django
    # models.
    errors: list[CheckMessage] = []

    entity_type = getattr(model, "entity_type", None)
    entity_type_plural = getattr(model, "entity_type_plural", None)

    # ``LinkableModel.__init_subclass__`` validates these at class-creation
    # time, but its abstract-detection ("``entity_type`` in ``cls.__dict__``")
    # is decoupled from Django's ``_meta.abstract``. A concrete-by-Django
    # subclass that simply forgot to declare ``entity_type`` slips past the
    # __init_subclass__ guard and lands here. Backstop it explicitly.
    if not isinstance(entity_type, str) or not entity_type:
        errors.append(
            Error(
                f"{model.__name__} inherits LinkableModel but does not "
                f"declare ``entity_type`` as a non-empty string.",
                obj=model,
                id="core.E106",
            )
        )
    else:
        prior = seen_entity_type.get(entity_type)
        if prior is not None:
            errors.append(
                Error(
                    f"Duplicate LinkableModel.entity_type {entity_type!r}: "
                    f"declared by {prior.__name__} and {model.__name__}.",
                    obj=model,
                    id="core.E101",
                )
            )
        else:
            seen_entity_type[entity_type] = model

    if not isinstance(entity_type_plural, str) or not entity_type_plural:
        errors.append(
            Error(
                f"{model.__name__} inherits LinkableModel but does not "
                f"declare ``entity_type_plural`` as a non-empty string.",
                obj=model,
                id="core.E107",
            )
        )
    else:
        prior = seen_entity_type_plural.get(entity_type_plural)
        if prior is not None:
            errors.append(
                Error(
                    f"Duplicate LinkableModel.entity_type_plural "
                    f"{entity_type_plural!r}: declared by {prior.__name__} "
                    f"and {model.__name__}.",
                    obj=model,
                    id="core.E102",
                )
            )
        else:
            seen_entity_type_plural[entity_type_plural] = model

    public_id_field = getattr(model, "public_id_field", None)
    if not isinstance(public_id_field, str) or not public_id_field:
        errors.append(
            Error(
                f"{model.__name__}.public_id_field must be a non-empty string.",
                obj=model,
                id="core.E103",
            )
        )
        return errors

    # Production callers (``check_linkable_models``) always pass a Django
    # model with ``_meta``; ``getattr`` keeps the duck-typed shape without a
    # narrower static type that would force ignores at the test stand-in
    # call sites.
    meta = getattr(model, "_meta", None)
    if meta is None:
        return errors
    try:
        field = meta.get_field(public_id_field)
    except FieldDoesNotExist:
        errors.append(
            Error(
                f"{model.__name__}.public_id_field={public_id_field!r} "
                f"does not name a field on the model.",
                obj=model,
                id="core.E104",
            )
        )
        return errors

    if not getattr(field, "unique", False):
        errors.append(
            Error(
                f"{model.__name__}.public_id_field={public_id_field!r} "
                f"must reference a field with unique=True.",
                obj=model,
                id="core.E105",
            )
        )

    return errors
