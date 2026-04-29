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
        self._register_picker_types()
        self._register_reference_cleanup()

    @staticmethod
    def _register_reference_cleanup() -> None:
        from django.apps import apps

        from apps.core.markdown import MarkdownField
        from apps.core.models import register_reference_cleanup

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
        """Register one ``LinkType`` per addressable catalog entity.

        Walks ``LinkableModel`` so every URL-addressable entity is renderable
        via ``[[<entity-type>:<public-id>]]`` markdown — even ones absent from the
        wikilink picker (Location). Picker presentation is a separate registry;
        see :meth:`_register_picker_types`.
        """
        from apps.core.wikilinks import LinkType, register

        from ._walks import linkable_models

        for model in linkable_models():
            register(
                LinkType(
                    name=model.entity_type,
                    model_path=f"catalog.{model.__name__}",
                    public_id_field=model.public_id_field,
                    url_pattern=model.link_url_pattern,
                    url_field="public_id",
                    label_field="name",
                )
            )

    @staticmethod
    def _register_picker_types() -> None:
        """Register one ``PickerType`` per catalog model that opts into the picker.

        Walks ``WikilinkableModel`` (a strict subset of ``LinkableModel``).
        Models that are URL-addressable but absent from the picker — Location
        is the live case — inherit ``LinkableModel`` only and so register a
        ``LinkType`` (renderer) but no ``PickerType``.
        """
        from apps.core.wikilinks import PickerType, register_picker

        from ._walks import wikilinkable_models

        for model in wikilinkable_models():
            label = model.link_label or str(model._meta.verbose_name).title()
            description = (
                model.link_description or f"Link to a {model._meta.verbose_name}"
            )
            register_picker(
                PickerType(
                    name=model.entity_type,
                    label=label,
                    description=description,
                    sort_order=model.link_sort_order,
                    model_path=f"catalog.{model.__name__}",
                    public_id_field=model.public_id_field,
                    autocomplete_search_fields=model.link_autocomplete_search_fields,
                    autocomplete_ordering=model.link_autocomplete_ordering,
                    autocomplete_select_related=model.link_autocomplete_select_related,
                    autocomplete_serialize=model.link_autocomplete_serialize,
                )
            )
