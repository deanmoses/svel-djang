"""Wikilink picker registry — the type-picker the markdown editor surfaces.

Sibling to :mod:`apps.core.wikilinks.types`, which owns the *renderer* registry
(every URL-addressable entity that ``[[<entity-type>:<public-id>]]`` can resolve to). This
module owns the *picker* registry — the strict subset of types the authoring
UI offers when a user types ``[[``.

Why two registries: the renderer needs to resolve any addressable entity
(``LinkableModel``); the picker only offers types we want users to author
against (``WikilinkableModel`` plus a few special cases like citations). The
two concerns share *some* runtime data (model class, autocomplete fields)
but are read by entirely separate consumers — keeping them apart prevents
the renderer from carrying nullable picker fields that downstream renderer
code has to keep ignoring.

The ``register_picker`` / ``get_picker_type`` / ``get_picker_types`` helpers
are re-exported by :mod:`apps.core.wikilinks` (the package ``__init__``);
prefer that import path from outside this module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from apps.core.schemas import LinkTargetSchema

FLOWS = ("standard", "custom")


@dataclass(frozen=True)
class PickerType:
    """One entry in the wikilink autocomplete picker.

    For ``flow="standard"`` types (the common case), the picker endpoint
    runs an autocomplete query against ``model_path`` using the
    ``autocomplete_*`` fields and serializes results via
    ``autocomplete_serialize``.

    For ``flow="custom"`` types (citations), the frontend handles the flow
    end-to-end; the standard-flow fields are unused.
    """

    name: str  # Registry key — must match the LinkType.name used by the renderer.
    label: str
    description: str
    sort_order: int = 100
    flow: str = "standard"

    # --- Standard-flow query config (unused when flow == "custom") ---
    model_path: str = ""  # "catalog.Manufacturer" — resolved via apps.get_model()
    public_id_field: str | None = None
    autocomplete_search_fields: tuple[str, ...] = ()
    autocomplete_ordering: tuple[str, ...] = ()
    autocomplete_select_related: tuple[str, ...] = ()
    autocomplete_serialize: Callable[[Any], LinkTargetSchema] | None = None

    # --- Runtime toggle (evaluated at usage time, not registration time) ---
    is_enabled: Callable[[], bool] = field(default=lambda: True)

    def get_model(self) -> type[Any]:
        """Resolve the model class lazily via Django's app registry.

        Returns ``type[Any]`` (not ``type[Model]``) so callers can read
        ``.objects`` without a ``# type: ignore`` — managers are added by
        Django's ``ModelBase`` to concrete subclasses, but django-stubs
        infers them on the abstract ``Model`` parent.
        """
        from django.apps import apps

        return apps.get_model(self.model_path)


_registry: dict[str, PickerType] = {}


def register_picker(picker_type: PickerType) -> None:
    """Register a picker type. Called from each app's ``AppConfig.ready()``."""
    if picker_type.name in _registry:
        raise ValueError(f"Picker type '{picker_type.name}' is already registered")
    if picker_type.flow not in FLOWS:
        raise ValueError(
            f"Picker type '{picker_type.name}': flow must be one of "
            f"{FLOWS}, got {picker_type.flow!r}"
        )
    _registry[picker_type.name] = picker_type


def clear_registry() -> None:
    """Reset registry state. For tests only."""
    _registry.clear()


def get_picker_type(name: str) -> PickerType | None:
    """Get a registered picker type by name, or None."""
    return _registry.get(name)


def get_picker_types() -> list[dict[str, str]]:
    """Return enabled picker types in display order, for the type-picker API."""
    types = sorted(
        (pt for pt in _registry.values() if pt.is_enabled()),
        key=lambda pt: pt.sort_order,
    )
    return [
        {
            "name": pt.name,
            "label": pt.label,
            "description": pt.description,
            "flow": pt.flow,
        }
        for pt in types
    ]
