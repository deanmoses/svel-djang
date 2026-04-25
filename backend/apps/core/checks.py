"""Project-wide Django system checks for ``apps.core``."""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.core import checks


@checks.register(checks.Tags.models)
def check_linkable_public_id_field_unique(
    app_configs: Any = None,  # noqa: ANN401 — Django check signature
    **kwargs: Any,  # noqa: ANN401 — Django check signature
) -> list[checks.CheckMessage]:
    """Every concrete LinkableModel's ``public_id_field`` must be ``unique=True``.

    Without this, ``LinkableModel.public_id`` would not identify a single row,
    breaking URL resolution and any consumer that looks up entities by their
    public identifier.
    """
    from apps.core.models import LinkableModel

    errors: list[checks.CheckMessage] = []
    for model in apps.get_models():
        if not issubclass(model, LinkableModel):
            continue
        if model._meta.abstract or model._meta.proxy:
            continue
        field_name = model.public_id_field
        try:
            field = model._meta.get_field(field_name)
        except Exception:
            errors.append(
                checks.Error(
                    f"{model.__name__}.public_id_field={field_name!r} does not "
                    f"name a field on the model.",
                    obj=model,
                    id="core.E001",
                )
            )
            continue
        if not getattr(field, "unique", False):
            errors.append(
                checks.Error(
                    f"{model.__name__}.public_id_field={field_name!r} must be "
                    f"declared with unique=True.",
                    obj=model,
                    id="core.E002",
                )
            )
    return errors
