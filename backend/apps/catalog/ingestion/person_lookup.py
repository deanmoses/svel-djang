"""Shared person-lookup helper for ingestion commands."""

from __future__ import annotations

import logging

from apps.catalog.models import Person, PersonAlias

logger = logging.getLogger(__name__)


def build_person_lookup() -> dict[str, Person]:
    """Return a ``{name.lower(): Person}`` dict including aliases.

    External ingest commands (IPDB, OPDB, Fandom, etc.) use this to match
    credit names to existing Person records.  Aliases from
    ``data/people.json`` allow alternative spellings (e.g. "Keith Johnson")
    to resolve to the canonical Person ("Keith P. Johnson").

    On collision (alias value matches an existing person's canonical name
    or another alias pointing to a different person), the alias is skipped
    with a warning.
    """
    lookup: dict[str, Person] = {p.name.lower(): p for p in Person.objects.all()}

    for alias in PersonAlias.objects.select_related("person").all():
        key = alias.value.lower()
        if key in lookup and lookup[key] != alias.person:
            logger.warning(
                "Alias %r for %s collides with existing person %s — skipping",
                alias.value,
                alias.person.name,
                lookup[key].name,
            )
            continue
        lookup[key] = alias.person

    return lookup
