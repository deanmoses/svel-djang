"""Abstract base for entities that can be targets of media attachments."""

from __future__ import annotations

from typing import ClassVar

from apps.provenance.models import ClaimControlledModel

__all__ = ["MediaSupported"]


class MediaSupported(ClaimControlledModel):
    """Mixin marking a model as a valid target for media attachments.

    Any model that inherits this mixin can have EntityMedia rows pointing
    at it via GenericFK. EntityMedia.clean() rejects content types that
    are not MediaSupported.

    Subclasses should set ``MEDIA_CATEGORIES`` to the list of allowed
    category strings for that entity type (e.g. ``["backglass", "playfield"]``).
    An empty list means the entity supports media but has no category vocabulary.

    Extends ``ClaimControlledModel`` because ``media_attachment`` is itself a
    claim field (see ``apps.catalog.claims.build_media_attachment_claim``):
    every ``MediaSupported`` entity is by construction a claim subject.  The
    inheritance encodes that structural commitment as a compile-time guarantee.
    """

    MEDIA_CATEGORIES: ClassVar[list[str]] = []

    class Meta:
        abstract = True
