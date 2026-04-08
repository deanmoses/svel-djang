"""Shared entity-type alias mapping.

Maps UI-facing entity type names to Django ContentType model names.
This exists because the Python class ``MachineModel`` produces the
ContentType name ``machinemodel``, but the UI-facing identifier is
``model``.

Used by any resolver that converts an API entity_type parameter to a
ContentType lookup (media API, edit-history, field-constraints,
recent-changes feed, etc.).
"""

# UI name → ContentType.model value
ENTITY_TYPE_ALIASES: dict[str, str] = {
    "model": "machinemodel",
}


def resolve_entity_type(entity_type: str) -> str:
    """Return the ContentType model name for an entity_type string.

    Checks the alias map first, then falls back to stripping hyphens
    (e.g. "corporate-entity" → "corporateentity").
    """
    return ENTITY_TYPE_ALIASES.get(entity_type, entity_type.replace("-", ""))
