"""Shared validators for catalog data."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError


def bulk_create_validated(
    model: Any,
    objs: list[Any],
    **kwargs: Any,
) -> Any:
    """Like ``model.objects.bulk_create()`` but runs mojibake validation first.

    Checks every field that has ``validate_no_mojibake`` in its validators
    and raises ``ValidationError`` if any value contains encoding corruption.
    Use this in ingestion commands instead of bare ``bulk_create()``.
    """
    checked_fields: list[Any] = [
        f
        for f in model._meta.get_fields()
        if hasattr(f, "validators")
        and hasattr(f, "attname")
        and validate_no_mojibake in f.validators
    ]
    if checked_fields:
        for obj in objs:
            for field in checked_fields:
                value = getattr(obj, field.attname, None)
                if value:
                    validate_no_mojibake(value)
    return model.objects.bulk_create(objs, **kwargs)


def validate_no_mojibake(value: object) -> None:
    """Reject text containing mojibake (encoding-corruption artifacts).

    Detects UTF-8 text that was misinterpreted as Latin-1 or Windows-1252
    by attempting to reverse the corruption. If re-encoding as cp1252 and
    decoding as UTF-8 produces different (valid) text, the original was
    garbled. Also rejects the Unicode replacement character (U+FFFD).

    Legitimate accented characters (é, ü, ñ) pass through fine.
    """
    if not isinstance(value, str) or not value:
        return

    if "\ufffd" in value:
        raise ValidationError(
            "Text contains a replacement character (�), indicating encoding corruption."
        )

    for encoding in ("cp1252", "latin-1"):
        try:
            recovered = value.encode(encoding).decode("utf-8")
        except UnicodeDecodeError, UnicodeEncodeError:
            continue
        if recovered != value:
            raise ValidationError(
                "Text contains mojibake (garbled encoding). "
                "Check for copy-paste artifacts or encoding issues."
            )
