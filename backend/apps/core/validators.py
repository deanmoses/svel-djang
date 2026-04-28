"""Shared validators for catalog data."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Field, Model
from django.utils import timezone


def bulk_create_validated[M: Model](
    model: type[M],
    objs: list[M],
    *,
    batch_size: int | None = None,
    ignore_conflicts: bool = False,
    update_conflicts: bool = False,
    update_fields: Collection[str] | None = None,
    unique_fields: Collection[str] | None = None,
) -> list[M]:
    """Like ``model.objects.bulk_create()`` but runs mojibake validation first.

    Checks every field that has ``validate_no_mojibake`` in its validators
    and raises ``ValidationError`` if any value contains encoding corruption.
    Use this in ingestion commands instead of bare ``bulk_create()``.
    """
    checked_fields: list[Field[Any, Any]] = [
        f
        for f in model._meta.get_fields()
        if isinstance(f, Field) and validate_no_mojibake in f.validators
    ]
    if checked_fields:
        for obj in objs:
            for field in checked_fields:
                value = getattr(obj, field.attname, None)
                if value:
                    validate_no_mojibake(value)

    # Django's auto_now does not fire during bulk_create, so refresh
    # updated_at manually on TimeStampedModel descendants. When
    # update_conflicts is in use, also ensure the column is in update_fields
    # so existing rows get the new value written back.
    from apps.core.models import TimeStampedModel  # avoid circular import

    if issubclass(model, TimeStampedModel):
        now = timezone.now()
        for obj in objs:
            assert isinstance(obj, TimeStampedModel)
            obj.updated_at = now
        if (
            update_conflicts
            and update_fields is not None
            and "updated_at" not in update_fields
        ):
            update_fields = [*update_fields, "updated_at"]

    return model._default_manager.bulk_create(
        objs,
        batch_size=batch_size,
        ignore_conflicts=ignore_conflicts,
        update_conflicts=update_conflicts,
        update_fields=update_fields,
        unique_fields=unique_fields,
    )


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
