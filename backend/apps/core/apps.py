from typing import Any

from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Core"

    def ready(self) -> None:
        from constance.signals import config_updated

        config_updated.connect(_on_constance_updated)


# Constance's config_updated signal passes arbitrary value types (whatever the
# changed setting holds — str, int, bool, etc.) and reserves the right to add
# keyword arguments, so this is a framework-owned callback surface.
def _on_constance_updated(
    sender: Any,  # noqa: ANN401 — constance signal sender
    key: str,
    old_value: Any,  # noqa: ANN401 — constance setting value, arbitrary type
    new_value: Any,  # noqa: ANN401 — constance setting value, arbitrary type
    **kwargs: Any,  # noqa: ANN401 — Django signal framework passthrough
) -> None:
    """Invalidate API caches when Constance settings change."""
    if key == "CONTENT_DISPLAY_POLICY":
        from apps.catalog.cache import invalidate_all

        invalidate_all()
