"""Signal handlers to invalidate cached /all/ endpoint data on model changes."""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save

from .cache import invalidate_all


def _invalidate_cache(sender, **kwargs):
    invalidate_all()


def connect():
    """Connect cache-invalidation signals. Called from AppConfig.ready()."""
    from .models import (
        Address,
        Credit,
        CorporateEntity,
        MachineModel,
        Manufacturer,
        Person,
        Title,
    )

    for model in (
        Address,
        MachineModel,
        Manufacturer,
        Person,
        CorporateEntity,
        Credit,
        Title,
    ):
        uid = f"invalidate_cache_{model.__name__}"
        post_save.connect(_invalidate_cache, sender=model, dispatch_uid=f"{uid}_save")
        post_delete.connect(
            _invalidate_cache, sender=model, dispatch_uid=f"{uid}_delete"
        )
