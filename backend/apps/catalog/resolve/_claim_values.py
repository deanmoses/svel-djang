"""Read-side TypedDict vocabulary for relationship-claim JSON payloads.

One TypedDict per distinct payload shape consumed by resolvers in this
package. Each TypedDict mirrors a :class:`RelationshipSchema` registered
in :mod:`apps.catalog.claims` — the consistency test in
``tests/test_claim_values.py`` enforces that mirror.

Resolvers ``cast(<Shape>, claim.value)`` at the top of their loop body;
reads stay on ``.get()`` until Step 5 of ResolveHardening flips required
keys to subscript.

``from __future__ import annotations`` is deliberately omitted — TypedDict
computes ``__required_keys__`` at class-creation time and cannot see
through stringified ``Required``/``NotRequired`` wrappers.
"""

from typing import NotRequired, Required, TypedDict


class GameplayFeatureClaimValue(TypedDict):
    """Payload for ``gameplay_feature`` relationship claims on MachineModel."""

    gameplay_feature: Required[int]
    exists: Required[bool]
    count: NotRequired[int | None]


class CreditClaimValue(TypedDict):
    """Payload for ``credit`` relationship claims on MachineModel / Series."""

    person: Required[int]
    role: Required[int]
    exists: Required[bool]


class AbbreviationClaimValue(TypedDict):
    """Payload for ``abbreviation`` relationship claims on Title / MachineModel."""

    value: Required[str]
    exists: Required[bool]


class AliasClaimValue(TypedDict):
    """Payload for ``*_alias`` relationship claims across all AliasModel subjects."""

    alias_value: Required[str]
    exists: Required[bool]
    alias_display: NotRequired[str]


class ParentClaimValue(TypedDict):
    """Payload for ``*_parent`` self-referential hierarchy claims."""

    parent: Required[int]
    exists: Required[bool]


class MediaAttachmentClaimValue(TypedDict):
    """Payload for ``media_attachment`` claims on every MediaSupportedModel subject."""

    media_asset: Required[int]
    exists: Required[bool]
    category: NotRequired[str | None]
    is_primary: NotRequired[bool]


class LocationClaimValue(TypedDict):
    """Payload for ``location`` relationship claims on CorporateEntity.

    Materializes CorporateEntityLocation rows; CorporateEntity has no
    ``location`` column. ``exists=False`` retracts the row.
    """

    location: Required[int]
    exists: Required[bool]
