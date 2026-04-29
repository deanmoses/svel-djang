"""Wikilink ``[[<entity-type>:<public-id>]]`` machinery — picker registration and the
abstract base catalog models inherit to opt into the picker.

Public surface: :class:`WikilinkableModel` (inherited by catalog models).

Picker internals (``PickerType`` + registry helpers) are also re-exported
here for the registration sites (``apps.catalog.apps``,
``apps.provenance.apps``) and the picker API (``apps.core.api``). Other
code should not import them.
"""

from apps.core.wikilinks.base import WikilinkableModel
from apps.core.wikilinks.picker import (
    PickerType,
    get_picker_type,
    get_picker_types,
    register_picker,
)

__all__ = [
    "PickerType",
    "WikilinkableModel",
    "get_picker_type",
    "get_picker_types",
    "register_picker",
]
