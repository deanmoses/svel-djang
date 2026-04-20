"""Soft-delete planning and execution for user-deletable catalog entities.

A user "delete" in this system is a ``status=deleted`` claim at user priority
rather than a DB row removal. The walker below enforces the spec's cascade
rules (see docs/plans/RecordCreateDelete.md §Cascade Behavior):

* CASCADE to an independent lifecycle entity — write ``status=deleted``
  claims for each active child in the same ChangeSet. Modeled here by an
  opt-in ``soft_delete_cascade_relations`` attribute on the parent model,
  because the DB FK may itself be PROTECT (e.g. ``MachineModel.title``).
* CASCADE to an owned child row with no lifecycle — do nothing. The child
  rides with the parent's visibility.
* PROTECT, referenced by an active independent entity — block. The user
  must resolve the reference before the delete can proceed.
* PROTECT, referenced only by soft-deleted (or non-lifecycle) entities —
  allow. The DB-level PROTECT stays as a safety net against hard deletes;
  this rule is enforced here, at the application layer, because the DB
  can't see ``status=deleted``.

The walker is generic over any entity with ``EntityStatusMixin``. Title is
the first caller; Model Delete and the rest will plug in by declaring
``soft_delete_cascade_relations`` on their models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from django.db import models as db_models

from apps.core.models import CatalogModel, EntityStatusMixin
from apps.provenance.models import ChangeSetAction

from .edit_claims import ClaimSpec, execute_multi_entity_claims
from .schemas import EditCitationInput


@dataclass(frozen=True)
class BlockingReferrer:
    """A live reference that prevents a soft-delete from proceeding."""

    entity_type: str  # canonical hyphenated CatalogModel.entity_type, e.g. "model"
    pk: int
    name: str
    slug: str | None
    relation: str  # field name on the referring model (e.g. "variant_of")
    blocked_target_type: str  # which entity in the cascade the referrer points at
    blocked_target_slug: str | None


def serialize_blocking_referrer(ref: BlockingReferrer) -> dict:
    """Wire format for :class:`BlockingReferrer` used by delete API responses."""
    return {
        "entity_type": ref.entity_type,
        "slug": ref.slug,
        "name": ref.name,
        "relation": ref.relation,
        "blocked_target_type": ref.blocked_target_type,
        "blocked_target_slug": ref.blocked_target_slug,
    }


@dataclass
class SoftDeletePlan:
    """Outcome of :func:`plan_soft_delete`.

    If ``blockers`` is non-empty, the delete cannot proceed and the caller
    should surface them to the user. Otherwise ``entities_to_delete`` is the
    ordered list to receive ``status=deleted`` claims in a single ChangeSet.
    """

    entities_to_delete: list = field(default_factory=list)
    blockers: list[BlockingReferrer] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return bool(self.blockers)


def _has_status(model_class: type[db_models.Model]) -> bool:
    return issubclass(model_class, EntityStatusMixin)


def _is_active(entity) -> bool:
    """An entity is active unless its resolved ``status`` is ``deleted``.

    Null status is treated as active (matches ``CatalogQuerySet.active``).
    """
    status = getattr(entity, "status", None)
    return status != "deleted"


def _entity_type(entity) -> str:
    """Canonical hyphenated entity_type for wire-format serialization.

    All soft-delete roots and blockers are CatalogModel subclasses today.
    If that ever changes, add an explicit policy here rather than silently
    leaking the Django-internal concatenated ``_meta.model_name``.
    """
    cls = type(entity)
    if not issubclass(cls, CatalogModel):
        raise TypeError(
            f"{cls.__name__} is not a CatalogModel; soft-delete wire format "
            "requires a canonical entity_type."
        )
    return cls.entity_type


def _entity_key(entity) -> tuple[str, int]:
    return (entity._meta.label_lower, entity.pk)


def _cascade_targets(root) -> list:
    """Walk ``soft_delete_cascade_relations`` to produce the ordered cascade.

    Deterministic order (parent before children, siblings by pk) so the
    resulting ChangeSet replays identically in tests.
    """
    result: list = []
    seen: set[tuple[str, int]] = set()
    stack: list = [root]
    while stack:
        entity = stack.pop(0)
        key = _entity_key(entity)
        if key in seen:
            continue
        seen.add(key)
        result.append(entity)
        relation_names: Iterable[str] = getattr(
            type(entity), "soft_delete_cascade_relations", ()
        )
        for rel_name in relation_names:
            manager = getattr(entity, rel_name)
            qs = manager.active().order_by("pk")
            stack.extend(qs)
    return result


def _iter_protect_referrers(entity):
    """Yield ``(referrer, relation_name)`` for active PROTECT referrers.

    Only referrers whose model has ``EntityStatusMixin`` count — PROTECT
    pointers from owned child rows (aliases, through tables, abbreviations)
    are ignored for soft-delete purposes (they ride with the parent).
    """
    for rel in type(entity)._meta.get_fields():
        if not rel.auto_created:
            continue
        if not (rel.one_to_many or rel.one_to_one):
            continue
        remote_field = rel.field  # ForeignKey on the remote model
        on_delete = remote_field.remote_field.on_delete
        if on_delete is db_models.PROTECT:
            remote_model = rel.related_model
            if not _has_status(remote_model):
                continue
            fk_name = remote_field.name
            qs = remote_model.objects.active().filter(**{fk_name: entity})
            for ref in qs:
                yield ref, fk_name
        elif on_delete in (db_models.SET_NULL, db_models.SET_DEFAULT):
            raise NotImplementedError(
                f"SET_NULL / SET_DEFAULT on {type(entity).__name__}.{rel.name} "
                "is not handled by the soft-delete walker. Add an explicit "
                "policy before enabling delete on a model with this relation."
            )
        # CASCADE branches are intentionally silent here: either the remote
        # model is in soft_delete_cascade_relations (handled elsewhere) or
        # it's an owned child that rides with parent visibility.


def plan_soft_delete(root) -> SoftDeletePlan:
    """Plan a soft-delete of *root* plus every active cascade child.

    Returns both the entities that would receive ``status=deleted`` claims
    and any active PROTECT referrers that would block the delete.
    """
    if not _has_status(type(root)):
        raise TypeError(
            f"{type(root).__name__} does not use EntityStatusMixin; "
            "soft-delete planning is not supported."
        )

    cascade = _cascade_targets(root)
    cascade_keys = {_entity_key(e) for e in cascade}

    blockers: list[BlockingReferrer] = []
    for entity in cascade:
        for ref, relation in _iter_protect_referrers(entity):
            if _entity_key(ref) in cascade_keys:
                continue
            blockers.append(
                BlockingReferrer(
                    entity_type=_entity_type(ref),
                    pk=ref.pk,
                    name=str(ref),
                    slug=getattr(ref, "slug", None),
                    relation=relation,
                    blocked_target_type=_entity_type(entity),
                    blocked_target_slug=getattr(entity, "slug", None),
                )
            )

    return SoftDeletePlan(entities_to_delete=cascade, blockers=blockers)


class SoftDeleteBlocked(Exception):
    """Raised by :func:`execute_soft_delete` when active references block it."""

    def __init__(self, blockers: list[BlockingReferrer]):
        self.blockers = blockers
        super().__init__(f"Blocked by {len(blockers)} active reference(s).")


def execute_soft_delete(
    root,
    *,
    user,
    note: str = "",
    citation: EditCitationInput | None = None,
):
    """Soft-delete *root* and all cascade children in one ChangeSet.

    Raises :class:`SoftDeleteBlocked` when an active PROTECT referrer would
    be left dangling. Returns ``(changeset, entities_deleted)`` on success.
    """
    plan = plan_soft_delete(root)
    if plan.is_blocked:
        raise SoftDeleteBlocked(plan.blockers)

    entries = [
        (entity, [ClaimSpec(field_name="status", value="deleted")])
        for entity in plan.entities_to_delete
        if _is_active(entity)
    ]
    if not entries:
        # Entity is already soft-deleted; no-op.
        return None, []

    changeset = execute_multi_entity_claims(
        entries,
        user=user,
        action=ChangeSetAction.DELETE,
        note=note,
        citation=citation,
    )
    return changeset, [entity for entity, _ in entries]
