from typing import Any

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Core"

    def ready(self) -> None:
        from constance.signals import config_updated

        config_updated.connect(_on_constance_updated)


def _on_constance_updated(
    sender: Any,
    key: str,
    old_value: Any,
    new_value: Any,
    **kwargs: Any,
) -> None:
    """Invalidate API caches when Constance settings change."""
    if key == "CONTENT_DISPLAY_POLICY":
        from apps.catalog.cache import invalidate_all

        invalidate_all()
