"""CatalogModel abstract base — marker for top-level catalog entities."""

from __future__ import annotations

from typing import ClassVar, Self

from apps.core.models import CatalogManager, EntityStatusMixin, LinkableModel
from apps.provenance.models import ClaimControlledModel

__all__ = ["CatalogModel"]


class CatalogModel(LinkableModel, EntityStatusMixin, ClaimControlledModel):
    """Abstract marker for top-level catalog entities.

    Combines URL-addressability (``LinkableModel``), claim-controlled
    lifecycle status (``EntityStatusMixin``), and claim-driven display
    fields (``ClaimControlledModel``). Used to distinguish catalog-specific
    code paths (e.g. ``ingest_pinbase``, soft-delete wire format) that must
    not widen to other ``LinkableModel`` subclasses.

    Concrete subclasses inherit all three capabilities transitively and do
    not relist them in their own bases. Each concrete subclass must still
    carry its own ``status_valid()`` constraint in ``Meta`` because Django
    does not inherit abstract-parent constraints when a concrete model
    defines its own ``Meta``.
    """

    # Re-declare ``objects`` here (originally on ``EntityStatusMixin``) so
    # ``Self`` rebinds at the catalog level. Without this, mypy resolves
    # ``model_cls.objects.active()`` (where ``model_cls: type[ModelT:
    # CatalogModel]``) by walking the type bound and binds ``Self`` to
    # ``EntityStatusMixin`` — the class where the descriptor is declared —
    # rather than ``ModelT``. Runtime is unaffected: same ``CatalogManager``
    # class, Django's ManagerDescriptor rebinds per concrete model anyway.
    # ``EntityStatusMixin.objects`` stays put so ``Location`` (which uses
    # the mixin without ``CatalogModel``) keeps its ``.active()`` queryset.
    objects: ClassVar[CatalogManager[Self]] = CatalogManager()

    class Meta:
        abstract = True
