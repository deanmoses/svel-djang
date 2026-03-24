from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        from constance.signals import config_updated

        config_updated.connect(_on_constance_updated)


def _on_constance_updated(sender, key, old_value, new_value, **kwargs):
    """Invalidate API caches when Constance settings change."""
    if key == "CONTENT_DISPLAY_POLICY":
        from apps.catalog.cache import invalidate_all

        invalidate_all()
