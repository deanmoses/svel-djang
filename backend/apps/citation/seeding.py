"""Seed canonical citation sources for known pinball reference works."""

from __future__ import annotations

from django.core.management.base import CommandError
from django.db import transaction

from apps.citation.seed_data import SEED_SOURCES as _SEED_SOURCES


def ensure_citation_sources(
    sources: list[dict] | None = None,
) -> dict[str, int]:
    """Seed citation sources. Returns {"created": N, "updated": N, "unchanged": N}.

    If sources is None, uses SEED_SOURCES (the canonical pinball reference data).
    Accepts a custom list for testing.
    """
    if sources is None:
        sources = _SEED_SOURCES

    counts: dict[str, int] = {"created": 0, "updated": 0, "unchanged": 0}

    with transaction.atomic():
        _seed_nodes(sources, parent=None, counts=counts)

    return counts


# Fields that are model columns (excluding children, links, and parent).
_SOURCE_FIELDS = frozenset(
    {
        "name",
        "source_type",
        "author",
        "publisher",
        "year",
        "month",
        "day",
        "date_note",
        "isbn",
        "description",
        "identifier_key",
    }
)


def _seed_nodes(
    nodes: list[dict],
    parent,
    counts: dict[str, int],
) -> None:
    from apps.citation.models import CitationSource, CitationSourceLink

    for node in nodes:
        children = node.get("children", [])
        links = node.get("links", [])
        fields = {k: v for k, v in node.items() if k in _SOURCE_FIELDS}
        fields["parent"] = parent

        # -- Look up existing record --
        isbn = fields.get("isbn")
        if isbn:
            obj = CitationSource.objects.filter(isbn=isbn).first()
        else:
            name = fields["name"]
            source_type = fields["source_type"]
            qs = CitationSource.objects.filter(name=name, source_type=source_type)
            count = qs.count()
            if count > 1:
                raise CommandError(
                    f"Multiple sources match ({name!r}, {source_type!r}) "
                    f"— resolve manually"
                )
            obj = qs.first()

        # -- Create or update --
        if obj is None:
            obj = CitationSource(**fields)
            obj.full_clean()
            obj.save()
            counts["created"] += 1
        else:
            # Compare fields, using parent_id for FK comparison
            defaults = {k: v for k, v in fields.items() if k != "parent"}
            changes = {k: v for k, v in defaults.items() if getattr(obj, k) != v}
            if fields["parent"] is not None:
                if obj.parent_id != fields["parent"].pk:
                    changes["parent"] = fields["parent"]
            elif obj.parent_id is not None:
                changes["parent"] = None

            if changes:
                for k, v in changes.items():
                    setattr(obj, k, v)
                obj.full_clean()
                obj.save(update_fields=[*changes.keys(), "updated_at"])
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1

        # -- Links --
        for link_data in links:
            url = link_data["url"]
            label = link_data.get("label", "")
            link_type = link_data["link_type"]
            existing = CitationSourceLink.objects.filter(
                citation_source=obj, url=url
            ).first()
            if existing is None:
                link_obj = CitationSourceLink(
                    citation_source=obj, url=url, label=label, link_type=link_type
                )
                link_obj.full_clean()
                link_obj.save()
            else:
                link_changes = {}
                if existing.label != label:
                    link_changes["label"] = label
                if existing.link_type != link_type:
                    link_changes["link_type"] = link_type
                if link_changes:
                    for k, v in link_changes.items():
                        setattr(existing, k, v)
                    existing.full_clean()
                    existing.save(update_fields=[*link_changes.keys(), "updated_at"])

        # -- Recurse into children --
        _seed_nodes(children, parent=obj, counts=counts)
