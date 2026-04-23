"""Shared Ninja schemas for the core app."""

from __future__ import annotations

from ninja import Schema


class LinkTypeSchema(Schema):
    """One entry in the autocomplete type picker."""

    name: str
    label: str
    description: str
    flow: str


class LinkTargetSchema(Schema):
    """Serialized shape for one autocomplete result.

    Returned by ``LinkType.autocomplete_serialize`` and consumed by the
    ``/link-types/targets/`` endpoint.
    """

    ref: str
    label: str


class LinkTargetsResponseSchema(Schema):
    """Response body for ``/link-types/targets/``."""

    results: list[LinkTargetSchema]
