from typing import Any

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    verbose_name = "Catalog"

    def ready(self) -> None:
        from . import signals
        from .claims import register_catalog_relationship_schemas

        signals.connect()
        register_catalog_relationship_schemas()
        self._register_link_types()
        self._register_reference_cleanup()

    @staticmethod
    def _register_reference_cleanup() -> None:
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
    def _register_link_types() -> None:
        from django.apps import apps

        from apps.core.markdown_links import LinkType, register
        from apps.core.models import LinkableModel
        from apps.core.schemas import LinkTargetSchema

        def _default_serialize(
            obj: Any,  # noqa: ANN401 - matches LinkType.autocomplete_serialize callback contract
        ) -> LinkTargetSchema:
            return LinkTargetSchema(ref=obj.public_id, label=str(obj.name))

        for model in apps.get_app_config("catalog").get_models():
            if not issubclass(model, LinkableModel) or model._meta.abstract:
                continue
            name = getattr(model, "link_type_name", model.__name__.lower())
            register(
                LinkType(
                    name=name,
                    model_path=f"catalog.{model.__name__}",
                    public_id_field=model.public_id_field,
                    label=getattr(
                        model, "link_label", str(model._meta.verbose_name).title()
                    ),
                    description=getattr(
                        model,
                        "link_description",
                        f"Link to a {model._meta.verbose_name}",
                    ),
                    url_pattern=model.link_url_pattern,
                    url_field="public_id",
                    label_field="name",
                    sort_order=getattr(model, "link_sort_order", 100),
                    autocomplete_search_fields=getattr(
                        model,
                        "link_autocomplete_search_fields",
                        ("name__icontains",),
                    ),
                    autocomplete_ordering=getattr(
                        model,
                        "link_autocomplete_ordering",
                        ("name",),
                    ),
                    autocomplete_select_related=getattr(
                        model,
                        "link_autocomplete_select_related",
                        (),
                    ),
                    autocomplete_serialize=getattr(
                        model,
                        "link_autocomplete_serialize",
                        _default_serialize,
                    ),
                )
            )
