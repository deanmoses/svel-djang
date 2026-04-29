"""Wikilink ``[[<entity-type>:<public-id>]]`` machinery.

Owns two parallel registries:

- :class:`LinkType` (``types`` module) — the renderer registry. Every
  URL-addressable entity ``[[type:ref]]`` can resolve to.
- :class:`PickerType` (``picker`` module) — the picker registry. The
  strict subset of types the authoring UI offers when a user types ``[[``.

Public surface for catalog code is :class:`WikilinkableModel`; everything
else is for registration sites (``apps.catalog.apps``,
``apps.provenance.apps``), the picker API (``apps.core.api``), and the
markdown package (``apps.core.markdown``).
"""

from apps.core.wikilinks.base import WikilinkableModel
from apps.core.wikilinks.picker import (
    PickerType,
    get_picker_type,
    get_picker_types,
    register_picker,
)
from apps.core.wikilinks.types import (
    LinkType,
    get_enabled_link_types,
    get_enabled_public_id_types,
    get_link_type,
    get_patterns,
    register,
)

__all__ = [
    "LinkType",
    "PickerType",
    "WikilinkableModel",
    "get_enabled_link_types",
    "get_enabled_public_id_types",
    "get_link_type",
    "get_patterns",
    "get_picker_type",
    "get_picker_types",
    "register",
    "register_picker",
]
