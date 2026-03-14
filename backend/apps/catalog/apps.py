from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    verbose_name = "Catalog"

    def ready(self):
        from . import signals

        signals.connect()
        self._register_link_types()
        self._register_reference_cleanup()

    @staticmethod
    def _register_reference_cleanup():
        from django.apps import apps

        from apps.core.models import MarkdownField, register_reference_cleanup

        models_with_markdown = [
            model
            for model in apps.get_app_config("catalog").get_models()
            if any(isinstance(f, MarkdownField) for f in model._meta.get_fields())
            and not model._meta.abstract
        ]
        if models_with_markdown:
            register_reference_cleanup(*models_with_markdown)

    @staticmethod
    def _register_link_types():
        from django.apps import apps

        from apps.core.markdown_links import LinkType, register
        from apps.core.models import Linkable

        for model in apps.get_app_config("catalog").get_models():
            if not issubclass(model, Linkable) or model._meta.abstract:
                continue
            name = getattr(model, "link_type_name", model.__name__.lower())
            verbose_plural = model._meta.verbose_name_plural.replace(" ", "-")
            register(
                LinkType(
                    name=name,
                    model_path=f"catalog.{model.__name__}",
                    slug_field="slug",
                    label=getattr(
                        model, "link_label", model._meta.verbose_name.title()
                    ),
                    description=getattr(
                        model,
                        "link_description",
                        f"Link to a {model._meta.verbose_name}",
                    ),
                    url_pattern=getattr(
                        model,
                        "link_url_pattern",
                        f"/{verbose_plural}/{{slug}}",
                    ),
                    url_field="slug",
                    label_field="name",
                    sort_order=getattr(model, "link_sort_order", 100),
                )
            )
