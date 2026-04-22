"""Generic create / delete / restore wiring for lifecycle catalog entities.

Lifts the shared plumbing originally grown in :mod:`taxonomy` — rate
limiting, name / slug validation and uniqueness, PROTECT-blocker
serialization, soft-delete execution, and restore — into two registrar
functions. Entity-specific shapes (detail queryset, serialize function,
response schema) are injected as callables so the same helpers can wire
routes for taxonomy entities *and* the richer Theme / GameplayFeature /
Series / Franchise / System schemas without duplicating code.

Public schema class names keep the ``Taxonomy`` prefix for OpenAPI
stability — consumers already depend on
``TaxonomyDeletePreviewSchema`` and ``TaxonomyDeleteResponseSchema``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.responses import Status
from ninja.security import django_auth

from apps.catalog.naming import normalize_catalog_name
from apps.provenance.models import ChangeSetAction
from apps.provenance.rate_limits import (
    CREATE_RATE_LIMIT_SPEC,
    DELETE_RATE_LIMIT_SPEC,
    check_and_record,
)
from apps.provenance.schemas import EditCitationInput

from .edit_claims import ClaimSpec, execute_claims
from .entity_create import (
    assert_name_available,
    assert_slug_available,
    create_entity_with_claims,
    validate_name,
    validate_slug_format,
)
from .schemas import BlockingReferrerSchema
from .soft_delete import (
    SoftDeleteBlockedError,
    count_entity_changesets,
    execute_soft_delete,
    plan_soft_delete,
    serialize_blocking_referrer,
)

# ---------------------------------------------------------------------------
# Schemas — names kept stable for OpenAPI consumers.
# ---------------------------------------------------------------------------


class TaxonomyCreateSchema(Schema):
    name: str
    slug: str
    note: str = ""
    citation: EditCitationInput | None = None


class TaxonomyDeleteSchema(Schema):
    note: str = ""
    citation: EditCitationInput | None = None


class TaxonomyRestoreSchema(Schema):
    note: str = ""
    citation: EditCitationInput | None = None


class TaxonomyDeletePreviewSchema(Schema):
    name: str
    slug: str
    changeset_count: int
    blocked_by: list[BlockingReferrerSchema] = []
    # 0 on leaf entities; non-zero only for parents (tech-gen, display-type)
    # whose active children would block the delete.
    active_children_count: int = 0
    # Populated on subgen/subtype so the UI can show a parent breadcrumb.
    parent_name: str | None = None
    parent_slug: str | None = None


class TaxonomyDeleteResponseSchema(Schema):
    """Success body for entity soft-delete.

    ``affected_slugs`` is always ``[obj.slug]`` for leaf entities — taxonomy
    deletes block rather than cascade — but the list shape keeps parity with
    ``ModelDeleteResponseSchema.affected_models`` (which can be >1 for the
    Title cascade) so the frontend delete helper can be shared.
    """

    changeset_id: int
    affected_slugs: list[str]


# ---------------------------------------------------------------------------
# Registrars
# ---------------------------------------------------------------------------


DetailQsFn = Callable[[], Any]
SerializeFn = Callable[[Any], dict]


def register_entity_delete_restore(
    router: Router,
    model_cls,
    *,
    detail_qs: DetailQsFn,
    serialize_detail: SerializeFn,
    response_schema: type[Schema],
    child_related_name: str | None = None,
    parent_field: str | None = None,
) -> None:
    """Attach delete-preview, delete, and restore routes to *router*.

    * ``detail_qs`` — callable returning the prefetched queryset used to
      re-read the entity after restore, passed to the response serializer.
    * ``serialize_detail`` — callable that converts an entity instance to a
      wire dict. For taxonomy this is a shared helper; Theme / GameplayFeature
      / Series inject their own detail serializers.
    * ``response_schema`` — Ninja schema used for restore's 200 body. Restore
      responds with the entity's full detail shape.
    * ``child_related_name`` — set on entities with active-child blocking
      (tech-gen → subgenerations, display-type → subtypes). The accessor
      name is the ``related_name=`` declared on the child FK.
    * ``parent_field`` — set on subgen/subtype so the preview surfaces the
      parent name / slug and restore refuses while the parent is deleted.
    """
    entity_label = model_cls.__name__
    friendly = model_cls.entity_type.replace("-", " ")
    friendly_sentence = friendly.capitalize()

    def _delete_preview(request, slug: str):
        obj = get_object_or_404(model_cls.objects.active(), slug=slug)
        plan = plan_soft_delete(obj)

        active_children = 0
        if child_related_name is not None:
            active_children = getattr(obj, child_related_name).active().count()

        is_blocked = plan.is_blocked or active_children > 0
        changeset_count = 0 if is_blocked else count_entity_changesets(obj)

        parent_name: str | None = None
        parent_slug: str | None = None
        if parent_field is not None:
            parent = getattr(obj, parent_field)
            parent_name = parent.name
            parent_slug = parent.slug

        return {
            "name": obj.name,
            "slug": obj.slug,
            "changeset_count": changeset_count,
            "blocked_by": [serialize_blocking_referrer(b) for b in plan.blockers],
            "active_children_count": active_children,
            "parent_name": parent_name,
            "parent_slug": parent_slug,
        }

    _delete_preview.__name__ = f"{entity_label.lower()}_delete_preview"
    router.get(
        "/{slug}/delete-preview/",
        auth=django_auth,
        response=TaxonomyDeletePreviewSchema,
        tags=["private"],
    )(_delete_preview)

    def _delete(request, slug: str, data: TaxonomyDeleteSchema):
        check_and_record(request.user, DELETE_RATE_LIMIT_SPEC)

        obj = get_object_or_404(model_cls.objects.active(), slug=slug)

        if child_related_name is not None:
            active_children = getattr(obj, child_related_name).active().count()
            if active_children > 0:
                # The empty ``blocked_by`` array is required — the shared
                # frontend classifier in delete-flow.ts only treats a 422
                # as a ``blocked`` outcome when ``blocked_by`` is present
                # as an array; otherwise it falls through to a generic
                # form error and loses the structured state.
                return Status(
                    422,
                    {
                        "detail": (
                            f"Cannot delete: {obj.name} has {active_children} "
                            f"active child"
                            f"{'ren' if active_children != 1 else ''}. "
                            "Delete those first."
                        ),
                        "blocked_by": [],
                        "active_children_count": active_children,
                    },
                )

        try:
            changeset, deleted = execute_soft_delete(
                obj, user=request.user, note=data.note, citation=data.citation
            )
        except SoftDeleteBlockedError as exc:
            return Status(
                422,
                {
                    "detail": (
                        "Cannot delete: active references would be left dangling."
                    ),
                    "blocked_by": [
                        serialize_blocking_referrer(b) for b in exc.blockers
                    ],
                    "active_children_count": 0,
                },
            )

        if changeset is None:
            return Status(422, {"detail": f"{friendly_sentence} is already deleted."})

        return {
            "changeset_id": changeset.pk,
            "affected_slugs": [e.slug for e in deleted if isinstance(e, model_cls)],
        }

    _delete.__name__ = f"{entity_label.lower()}_delete"
    router.post(
        "/{slug}/delete/",
        auth=django_auth,
        response={200: TaxonomyDeleteResponseSchema, 422: dict},
        tags=["private"],
    )(_delete)

    def _restore(request, slug: str, data: TaxonomyRestoreSchema):
        check_and_record(request.user, CREATE_RATE_LIMIT_SPEC)

        # Bypass .active() — we're looking for soft-deleted rows.
        obj = get_object_or_404(model_cls, slug=slug)
        if obj.status != "deleted":
            return Status(422, {"detail": f"{friendly_sentence} is not deleted."})

        if parent_field is not None:
            parent = getattr(obj, parent_field)
            if parent.status == "deleted":
                return Status(
                    422,
                    {"detail": f"Restore {parent.name} first."},
                )

        execute_claims(
            obj,
            [ClaimSpec(field_name="status", value="active")],
            user=request.user,
            action=ChangeSetAction.EDIT,
            note=data.note,
            citation=data.citation,
        )

        refreshed = get_object_or_404(detail_qs(), slug=slug)
        return serialize_detail(refreshed)

    _restore.__name__ = f"{entity_label.lower()}_restore"
    router.post(
        "/{slug}/restore/",
        auth=django_auth,
        response={200: response_schema, 422: dict, 404: dict},
        tags=["private"],
    )(_restore)


def register_entity_create(
    router: Router,
    model_cls,
    *,
    detail_qs: DetailQsFn,
    serialize_detail: SerializeFn,
    response_schema: type[Schema],
    parent_field: str | None = None,
    parent_model: Any = None,
    route_suffix: str = "",
    scope_filter_builder: Callable[[Any], Q] | None = None,
    include_deleted_name_check: bool = False,
) -> None:
    """Attach a POST create route.

    When *parent_field* is None, mounts ``POST /`` on the entity's own
    router. Otherwise all three parent-related args must be supplied
    together and the route mounts at ``POST /{parent_slug}/<route_suffix>/``
    on the *parent's* router — mirroring the Title → Model nesting.

    FK claim values are stored as the parent's slug string, matching the
    shipped convention (see titles.py:1091 and the ``claim_fk_lookups``
    contract validated at provenance/validation.py:286).

    *scope_filter_builder* (parented mode only) narrows the name-collision
    scan to rows related to the resolved parent. Required for entities
    whose names are unique per-parent rather than globally (e.g.
    CorporateEntity: two manufacturers may each own a "Productions"
    entity, but not the same manufacturer). Receives the resolved parent
    instance and returns a ``Q`` to pass to ``assert_name_available``.

    *include_deleted_name_check* forwards to ``assert_name_available``'s
    ``include_deleted``. Required for entities whose ``name`` column is
    DB-unique (e.g. ``Manufacturer.name``) to avoid misreporting a
    soft-deleted-name collision as a slug collision.
    """
    parented = parent_field is not None
    if parented and not (parent_model and route_suffix):
        raise TypeError(
            "register_entity_create: when parent_field is set, "
            "parent_model and route_suffix are required."
        )
    if scope_filter_builder is not None and not parented:
        raise TypeError(
            "register_entity_create: scope_filter_builder requires parent_field."
        )

    entity_label = model_cls.__name__
    name_max = model_cls._meta.get_field("name").max_length
    friendly = model_cls.entity_type.replace("-", " ")

    def _do_create(request, data: TaxonomyCreateSchema, parent=None):
        check_and_record(request.user, CREATE_RATE_LIMIT_SPEC)

        name = validate_name(data.name, max_length=name_max)
        slug = validate_slug_format(data.slug)
        scope_filter = (
            scope_filter_builder(parent)
            if scope_filter_builder is not None and parent is not None
            else None
        )
        assert_name_available(
            model_cls,
            name,
            normalize=normalize_catalog_name,
            scope_filter=scope_filter,
            friendly_label=friendly,
            include_deleted=include_deleted_name_check,
        )
        assert_slug_available(model_cls, slug)

        row_kwargs: dict = {"name": name, "slug": slug, "status": "active"}
        claim_specs = [
            ClaimSpec(field_name="name", value=name),
            ClaimSpec(field_name="slug", value=slug),
            ClaimSpec(field_name="status", value="active"),
        ]
        if parent is not None:
            assert parent_field is not None
            row_kwargs[parent_field] = parent
            # FK claim value is the parent's slug string.
            claim_specs.append(ClaimSpec(field_name=parent_field, value=parent.slug))

        create_entity_with_claims(
            model_cls,
            row_kwargs=row_kwargs,
            claim_specs=claim_specs,
            user=request.user,
            note=data.note,
            citation=data.citation,
        )

        created = get_object_or_404(detail_qs(), slug=slug)
        return Status(201, serialize_detail(created))

    if parented:
        assert parent_model is not None

        def _create_parented(request, parent_slug: str, data: TaxonomyCreateSchema):
            parent = get_object_or_404(parent_model.objects.active(), slug=parent_slug)
            return _do_create(request, data, parent=parent)

        path = f"/{{parent_slug}}/{route_suffix}/"
        create_view = _create_parented
    else:

        def _create_unparented(request, data: TaxonomyCreateSchema):
            return _do_create(request, data)

        path = "/"
        create_view = _create_unparented

    create_view.__name__ = f"{entity_label.lower()}_create"
    router.post(
        path,
        auth=django_auth,
        response={201: response_schema},
        tags=["private"],
    )(create_view)
