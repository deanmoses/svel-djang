"""Abstract base for entities whose display fields are claim-controlled."""

from __future__ import annotations

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

__all__ = ["ClaimControlledModel"]


class ClaimControlledModel(models.Model):
    """Abstract base for entities whose display fields are claim-controlled.

    Declares the reverse-accessor to provenance claims and the typed ``slug``
    / ``name`` shape that claim-resolver helpers read generically.  Does NOT
    imply URL-addressability, globally-unique slugs, or status tracking —
    those are ``LinkableModel`` / ``SluggedModel`` / ``EntityStatusMixin``
    concerns and are layered in independently at the concrete class.

    **Diamond-inheritance constraint — do not weaken without refactoring.**
    Concrete catalog models combine ``CatalogModel`` and ``MediaSupported``,
    both of which extend ``ClaimControlledModel``, so this class is reached
    via two abstract paths.  The diamond is safe today only because every
    name-bearing thing here is either a ``GenericRelation`` (routed into
    ``_meta.private_fields`` by ``contribute_to_class(..., private_only=True)``
    and skipped by Django's clash check) or a bare type annotation (no
    Django field, no ``_meta`` registration).  Adding any non-private field
    here — anything that lands in ``_meta.local_fields`` or
    ``_meta.local_many_to_many``, e.g. a regular ``CharField`` or ``FK`` —
    would trigger ``FieldError("clashes with field of the same name")`` at
    concrete-model construction.  If you need to add such a field, refactor
    the diamond first (e.g. lift the field higher, or break the inheritance).
    """

    # Instance-level annotations let ``type[ClaimControlledModel]`` code read
    # ``.slug`` / ``.name`` without casting.  Concrete subclasses declare the
    # actual CharField / SlugField with their own max_length and validators.
    slug: str
    name: str

    claims = GenericRelation("provenance.Claim")

    class Meta:
        abstract = True
