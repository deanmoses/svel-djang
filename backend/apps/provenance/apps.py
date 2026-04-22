from __future__ import annotations

from typing import Any

from django.apps import AppConfig


def _format_citation_link(obj: Any, index: int, base_url: str, plain_text: bool) -> str:
    """Render a citation marker as a superscript footnote number."""
    if obj is None:
        return "[?]" if plain_text else "<sup>[?]</sup>"
    if plain_text:
        return f"[{index}]"
    return (
        f'<sup data-cite-id="{obj.pk}" data-cite-index="{index}"'
        f' tabindex="0" role="button">[{index}]</sup>'
    )


def _collect_citation_metadata(obj: Any, index: int) -> dict[str, Any]:
    """Collect structured metadata for a citation instance.

    Called by core's render pipeline via the collect_metadata callback.
    Core never inspects the returned dict — this is provenance-owned logic.
    """
    return {
        "id": obj.pk,
        "index": index,
        "source_name": obj.citation_source.name,
        "source_type": obj.citation_source.source_type,
        "author": obj.citation_source.author,
        "year": obj.citation_source.year,
        "locator": obj.locator,
        "links": [
            {"url": link.url, "label": link.label}
            for link in obj.citation_source.links.all()
        ],
    }


class ProvenanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.provenance"
    verbose_name = "Provenance"

    def ready(self) -> None:
        from apps.core.markdown_links import LinkType, register

        register(
            LinkType(
                name="cite",
                model_path="provenance.CitationInstance",
                label="Citation",
                description="Cite a source (book, web, magazine)",
                slug_field=None,
                format_link=_format_citation_link,
                collect_metadata=_collect_citation_metadata,
                select_related=("citation_source",),
                prefetch_related=("citation_source__links",),
                sort_order=1,
                autocomplete_flow="custom",
            )
        )
