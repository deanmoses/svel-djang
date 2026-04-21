"""Shared helpers for user-driven catalog record creation.

Title Create was the first instance of the pattern; Model Create is the
second. These helpers were extracted once a second caller existed to
prove the shape fits more than one entity. Subsequent record types (Person,
Manufacturer, …) should reuse these rather than copy-pasting.

What lives here:

* Slug format validation (regex + length).
* Generic name / slug availability pre-checks parameterized by model class
  and an optional scope filter (for entities whose collision rules are
  scoped, e.g. Model names are scoped to parent Title).
* A ``create_entity_with_claims`` wrapper that owns the transactional unit
  of work: row creation, ChangeSet + claims, and TOCTOU-safe translation
  of a DB unique-constraint violation into a field-level slug error.

What does not live here: name normalization (see ``apps.catalog.naming``),
rate limiting (see ``apps.provenance.rate_limits``), or the claim
machinery itself (see :mod:`.edit_claims`).
"""

from __future__ import annotations

import re
from typing import Callable

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.provenance.models import ChangeSetAction
from apps.provenance.schemas import EditCitationInput

from .edit_claims import (
    ClaimSpec,
    StructuredValidationError,
    execute_claims,
)

# Slug format is globally consistent across catalog record types: lowercase
# ASCII letters/digits, single hyphens between segments, no leading/trailing
# or repeated hyphens. The DB enforces uniqueness; this regex enforces shape.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG_LENGTH = 300


def validate_slug_format(slug: str) -> str:
    """Return *slug* stripped, or raise a field-level 422 on bad shape."""
    slug = (slug or "").strip()
    if not slug:
        raise StructuredValidationError(
            message="Slug cannot be blank.",
            field_errors={"slug": "Slug cannot be blank."},
        )
    if len(slug) > MAX_SLUG_LENGTH:
        raise StructuredValidationError(
            message="Slug too long.",
            field_errors={
                "slug": f"Slug must be {MAX_SLUG_LENGTH} characters or fewer."
            },
        )
    if not SLUG_RE.match(slug):
        raise StructuredValidationError(
            message="Invalid slug.",
            field_errors={
                "slug": (
                    "Slug may contain only lowercase letters, digits, and "
                    "hyphens, with no leading, trailing, or repeated hyphens."
                )
            },
        )
    return slug


def validate_name(name: str, *, max_length: int) -> str:
    """Return *name* stripped, or raise a field-level 422 on blank/overlong."""
    name = (name or "").strip()
    if not name:
        raise StructuredValidationError(
            message="Name cannot be blank.",
            field_errors={"name": "Name cannot be blank."},
        )
    if len(name) > max_length:
        raise StructuredValidationError(
            message="Name too long.",
            field_errors={"name": f"Name must be {max_length} characters or fewer."},
        )
    return name


def _resolve_alias_relation(model_cls):
    """Return ``(alias_model, parent_fk_name)`` if *model_cls* exposes an
    ``aliases`` reverse manager, else ``None``.

    Catalog alias models inherit from :class:`apps.core.models.AliasBase`
    (value column + ``related_name="aliases"`` on the parent FK). Using
    ``_meta.related_objects`` instead of ``getattr`` on the class keeps
    the lookup robust across model reloads and avoids hardcoding FK
    field names per entity (``theme``, ``reward_type``, ``feature``, …).
    """
    for rel in model_cls._meta.related_objects:
        if rel.get_accessor_name() == "aliases":
            return rel.related_model, rel.field.name
    return None


def assert_name_available(
    model_cls,
    name: str,
    *,
    normalize: Callable[[str], str],
    scope_filter: Q | None = None,
    exclude_pk: int | None = None,
    friendly_label: str,
    include_deleted: bool = False,
) -> None:
    """Raise a field-level 422 if *name* collides with an existing record.

    Names are compared after passing through *normalize* — typically
    :func:`apps.catalog.naming.normalize_catalog_name`. The normalization
    rule is shared with the frontend so the UI's "search returned zero
    results" signal and the API's enforcement stay in sync.

    *scope_filter* narrows the collision set. ``None`` means "all active
    records" (Title). For Model, pass ``Q(title_id=title.pk)`` so two
    titles can legitimately share a model name.

    *friendly_label* is the noun shown to the user, e.g. "title" or
    "model": "A model named 'Pro' already exists."

    *include_deleted* extends the collision scan to soft-deleted rows.
    Required for any entity whose ``name`` column is DB-unique (e.g.
    ``System.name``, ``Manufacturer.name``): a name that collides with a
    soft-deleted row would otherwise pass this pre-check and trip the DB
    unique constraint, which ``create_entity_with_claims`` misreports as a
    slug collision. With this flag set, the collision surfaces as a
    field-level name error before the insert is attempted.

    The alias-collision scan below does NOT follow ``include_deleted`` —
    it continues to filter ``parent__status=active``. Aliases have their
    own uniqueness (per-parent), separate from the parent ``name`` UNIQUE
    constraint, so they don't contribute to the IntegrityError this flag
    exists to prevent. If a future entity needs alias collisions against
    soft-deleted parents to count, extend both scans together.

    When *model_cls* exposes an ``aliases`` reverse manager (Theme,
    GameplayFeature, RewardType, …), aliases of active parents also count
    as collisions — the spec requires aliases to behave like alternate
    names for duplicate-prevention purposes. See
    docs/plans/RecordCreateDelete.md:115.
    """
    normalized = normalize(name)
    if not normalized:
        raise StructuredValidationError(
            message="Name cannot be blank.",
            field_errors={"name": "Name cannot be blank."},
        )

    qs = model_cls.objects.all() if include_deleted else model_cls.objects.active()
    if scope_filter is not None:
        qs = qs.filter(scope_filter)
    for pk, other_name in qs.values_list("pk", "name"):
        if exclude_pk is not None and pk == exclude_pk:
            continue
        if normalize(other_name) == normalized:
            raise StructuredValidationError(
                message="Name collision.",
                field_errors={
                    "name": (
                        f"A {friendly_label} named {other_name!r} already "
                        "exists. Pick a disambiguating name."
                    )
                },
            )

    alias_rel = _resolve_alias_relation(model_cls)
    if alias_rel is None:
        return
    alias_model, parent_fk_name = alias_rel
    alias_qs = alias_model.objects.filter(**{f"{parent_fk_name}__status": "active"})
    if scope_filter is not None:
        # Rewrite the scope filter so it applies to the alias's parent.
        alias_qs = alias_qs.filter(
            _rewrite_scope_for_alias(scope_filter, parent_fk_name)
        )
    for parent_pk, alias_value in alias_qs.values_list(f"{parent_fk_name}_id", "value"):
        if exclude_pk is not None and parent_pk == exclude_pk:
            continue
        if normalize(alias_value) == normalized:
            raise StructuredValidationError(
                message="Name collision.",
                field_errors={
                    "name": (
                        f"An alias {alias_value!r} already points at an "
                        f"existing {friendly_label}. Pick a disambiguating name."
                    )
                },
            )


def _rewrite_scope_for_alias(scope_filter: Q, parent_fk_name: str) -> Q:
    """Prefix each leaf lookup in *scope_filter* with ``{parent_fk_name}__``.

    The caller's ``scope_filter`` targets fields on the parent model
    (``title_id=...``); when applied against the alias table those same
    fields live behind the FK to the parent.
    """

    def _walk(node):
        new = Q()
        new.connector = node.connector
        new.negated = node.negated
        for child in node.children:
            if isinstance(child, Q):
                new.children.append(_walk(child))
            else:
                lookup, value = child
                new.children.append((f"{parent_fk_name}__{lookup}", value))
        return new

    return _walk(scope_filter)


def assert_slug_available(model_cls, slug: str) -> None:
    """Raise a field-level 422 if *slug* is already taken on *model_cls*.

    Slug uniqueness is DB-enforced (including against soft-deleted rows,
    whose DB rows still exist). This pre-check produces a nice field-scoped
    error for the common case; the DB constraint remains the authoritative
    backstop and is translated to the same shape by
    :func:`create_entity_with_claims` if a concurrent create wins the race.
    """
    if model_cls.objects.filter(slug=slug).exists():
        raise StructuredValidationError(
            message="Slug collision.",
            field_errors={
                "slug": f"The slug {slug!r} is already taken. Edit the slug field."
            },
        )


def create_entity_with_claims(
    model_cls,
    *,
    row_kwargs: dict,
    claim_specs: list[ClaimSpec],
    user,
    note: str = "",
    citation: EditCitationInput | None = None,
):
    """Create a new catalog row + its initial claims atomically.

    * Opens a ``transaction.atomic`` block so that a claim-write failure
      rolls the row back (and vice versa).
    * Creates the row via ``model_cls.objects.create(**row_kwargs)``.
    * Writes a user ChangeSet with ``action=create`` and the given
      *claim_specs* via :func:`.edit_claims.execute_claims`.
    * Translates a DB ``IntegrityError`` on the slug into the same
      field-level 422 that the pre-check produces. This covers the tiny
      TOCTOU window between ``assert_slug_available`` and the insert.

    Callers are responsible for name/slug validation and rate-limiting
    before invoking this helper. ``row_kwargs`` must contain ``slug`` —
    it's the only unique-constrained column this helper expects to be
    writing, and its value is echoed into the TOCTOU fallback error.

    .. warning::

        The IntegrityError handler unconditionally reports "slug
        collision." If *row_kwargs* ever includes another unique-
        constrained column (e.g. ``opdb_id`` on MachineModel) that trips
        the constraint, the user will see a misleading slug error.
        Callers must not pass such columns through this helper.
    """
    slug = row_kwargs["slug"]
    try:
        with transaction.atomic():
            entity = model_cls.objects.create(**row_kwargs)
            execute_claims(
                entity,
                claim_specs,
                user=user,
                action=ChangeSetAction.CREATE,
                note=note,
                citation=citation,
            )
    except IntegrityError:
        raise StructuredValidationError(
            message="Slug collision.",
            field_errors={
                "slug": f"The slug {slug!r} is already taken. Edit the slug field."
            },
        )
    return entity
