"""``WikilinkableModel`` — the abstract base catalog models inherit to
appear in the wikilink autocomplete picker.

Inheriting opts a model into the ``[[<entity-type>:<public-id>]]`` autocomplete picker
surfaced by the markdown editor. Models that are URL-addressable but
must not appear in the picker (e.g. Location) inherit
:class:`apps.core.models.LinkableModel` only, not this base.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from apps.core.models import LinkableModel
from apps.core.schemas import LinkTargetSchema


def _default_link_serialize(linkable: LinkableModel) -> LinkTargetSchema:
    """Default serializer for autocomplete results."""
    return LinkTargetSchema(ref=linkable.public_id, label=linkable.name)


class WikilinkableModel(LinkableModel):
    """A :class:`LinkableModel` that opts into the wikilink picker.

    ``link_label`` / ``link_description`` carry the empty-string sentinel as
    their declared default; the registration loop in
    :meth:`apps.catalog.apps.CatalogConfig._register_picker_types`
    materializes the real fallbacks from ``model._meta.verbose_name`` at
    app-ready time, when Django's ``_meta`` is fully wired (it is not yet
    wired during ``__init_subclass__``).
    """

    link_sort_order: ClassVar[int] = 100
    link_label: ClassVar[str] = ""
    link_description: ClassVar[str] = ""
    link_autocomplete_search_fields: ClassVar[tuple[str, ...]] = ("name__icontains",)
    link_autocomplete_ordering: ClassVar[tuple[str, ...]] = ("name",)
    link_autocomplete_select_related: ClassVar[tuple[str, ...]] = ()
    link_autocomplete_serialize: ClassVar[
        Callable[[LinkableModel], LinkTargetSchema]
    ] = staticmethod(_default_link_serialize)

    class Meta:
        abstract = True
