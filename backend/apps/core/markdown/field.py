"""``MarkdownField`` and the conversion path that doesn't touch ``RecordReference``.

Catalog model files import :class:`MarkdownField` from here. This module
intentionally does not import :mod:`apps.core.markdown.references`, so
including a ``MarkdownField`` on a model never drags in the reference
graph.
"""

from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.validators import validate_no_mojibake as _validate_no_mojibake
from apps.core.wikilinks import (
    LinkType,
    get_enabled_public_id_types,
    get_patterns,
)


class MarkdownField(models.TextField[str, str]):
    """A TextField containing markdown with ``[[<entity-type>:<public-id>]]`` links.

    The system introspects models for MarkdownField instances to:
    - Auto-discover which fields need reference syncing
    - Auto-generate ``{field}_html`` rendered output in API responses

    Includes ``validate_no_mojibake`` as a default validator to reject
    encoding-corrupted text at the model level.
    """

    default_validators = [_validate_no_mojibake]

    # Django's migration protocol; see Field.deconstruct.
    def deconstruct(self) -> Any:  # noqa: ANN401
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.TextField", args, kwargs


def get_markdown_fields(model: type[models.Model]) -> list[str]:
    """Return field names of all MarkdownField instances on a model."""
    return [f.name for f in model._meta.get_fields() if isinstance(f, MarkdownField)]


# ---------------------------------------------------------------------------
# Authoring <-> Storage conversion
# ---------------------------------------------------------------------------


def convert_authoring_to_storage(content: str) -> str:
    """Convert authoring format links to storage format.

    Only affects public-id-based types; ID-based types are already in storage format.

    Raises:
        ValidationError: If any linked target doesn't exist
    """
    if not content:
        return content

    errors: list[str] = []
    for lt in get_enabled_public_id_types():
        pats = get_patterns(lt)
        content = _convert_to_storage(content, lt, pats["authoring"], errors)

    if errors:
        raise ValidationError(errors)
    return content


def _convert_to_storage(
    content: str,
    lt: LinkType,
    pattern: re.Pattern[str],
    errors: list[str],
) -> str:
    """Convert ``[[type:public_id]]`` to ``[[type:id:N]]`` for one link type."""
    matches = list(pattern.finditer(content))
    if not matches:
        return content

    model = lt.get_model()
    raw_values = [m.group(1) for m in matches]

    if lt.public_id_field is None:
        raise ValueError(f"LinkType '{lt.name}' is not public-id-based")
    by_key: dict[str, models.Model]
    if lt.authoring_lookup:
        by_key = lt.authoring_lookup(model, raw_values)
    else:
        qs = model.objects.filter(**{f"{lt.public_id_field}__in": raw_values})
        by_key = {getattr(obj, lt.public_id_field): obj for obj in qs}

    result = content
    for match in reversed(matches):
        key = match.group(1)
        obj = by_key.get(key)
        if obj:
            result = (
                result[: match.start()]
                + f"[[{lt.name}:id:{obj.pk}]]"
                + result[match.end() :]
            )
        else:
            errors.append(f"{lt.name.title()} not found: [[{lt.name}:{key}]]")
            result = result[: match.start()] + match.group(0) + result[match.end() :]
    return result


def convert_storage_to_authoring(content: str) -> str:
    """Convert storage format links to authoring format for editing.

    Only affects public-id-based types; ID-based types are the same in both formats.
    """
    if not content:
        return content

    for lt in get_enabled_public_id_types():
        pats = get_patterns(lt)
        content = _convert_to_authoring(content, lt, pats["storage"])
    return content


def _convert_to_authoring(
    content: str,
    lt: LinkType,
    pattern: re.Pattern[str],
) -> str:
    """Convert ``[[type:id:N]]`` to ``[[type:public_id]]`` for one link type."""
    if lt.public_id_field is None:
        raise ValueError(f"LinkType '{lt.name}' is not public-id-based")
    matches = list(pattern.finditer(content))
    if not matches:
        return content

    model = lt.get_model()
    ids = [int(m.group(1)) for m in matches]
    by_id = {obj.pk: obj for obj in model.objects.filter(pk__in=ids)}

    result = content
    for match in reversed(matches):
        obj_id = int(match.group(1))
        obj = by_id.get(obj_id)
        if obj:
            if lt.get_authoring_key:
                key = lt.get_authoring_key(obj)
            else:
                key = getattr(obj, lt.public_id_field)
            result = (
                result[: match.start()] + f"[[{lt.name}:{key}]]" + result[match.end() :]
            )
        else:
            # Keep storage format for broken links (target deleted)
            result = result[: match.start()] + match.group(0) + result[match.end() :]
    return result


def prepare_markdown_claim_value(
    field_name: str, value: object, model_class: type[models.Model]
) -> object:
    """Convert authoring-format links to storage format if the field is a MarkdownField.

    Intended as the single integration point for all write paths (admin,
    API PATCH, ingestion) that store markdown content as claim values.

    Returns the value unchanged if the field is not a MarkdownField or
    the value is not a non-empty string.

    Raises :exc:`~django.core.exceptions.ValidationError` if any linked
    targets don't exist.
    """
    if (
        isinstance(value, str)
        and value
        and field_name in get_markdown_fields(model_class)
    ):
        return convert_authoring_to_storage(value)
    return value
