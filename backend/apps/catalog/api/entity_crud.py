"""Generic create / delete / restore wiring for lifecycle catalog entities.

Lifts the shared plumbing originally grown in :mod:`taxonomy` — rate
limiting, name / slug validation and uniqueness, PROTECT-blocker
serialization, soft-delete execution, and restore — into two registrar
functions. Entity-specific shapes (detail queryset, serialize function,
response schema) are injected as callables so the same helpers can wire
routes for taxonomy entities *and* the richer Theme / GameplayFeature /
Series / Franchise / System schemas without duplicating code.

All wire schemas used here — ``CreateSchema``, ``ChangeSetInputSchema``,
``TaxonomyDeletePreviewSchema``, ``DeleteResponseSchema`` — live in the
shared catalog/provenance schema modules. This module owns no schemas of
its own.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db import models as db_models
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.responses import Status
from ninja.security import django_auth

from apps.catalog.models import CatalogModel
from apps.catalog.naming import normalize_catalog_name
from apps.core.schemas import (
    ErrorDetailSchema,
    RateLimitErrorSchema,
    ValidationErrorSchema,
)
from apps.provenance.models import ChangeSetAction
from apps.provenance.rate_limits import (
    CREATE_RATE_LIMIT_SPEC,
    DELETE_RATE_LIMIT_SPEC,
    check_and_record,
)
from apps.provenance.schemas import ChangeSetInputSchema

from .edit_claims import ClaimSpec, execute_claims
from .entity_create import (
    assert_name_available,
    assert_slug_available,
    create_entity_with_claims,
    validate_name,
    validate_slug_format,
)
from .schemas import (
    AlreadyDeletedSchema,
    DeleteResponseSchema,
    EntityCreateInputSchema,
    EntityRef,
    SoftDeleteBlockedSchema,
    TaxonomyDeletePreviewSchema,
)
from .soft_delete import (
    SoftDeleteBlockedError,
    count_entity_changesets,
    execute_soft_delete,
    plan_soft_delete,
    serialize_blocking_referrer,
)

# ---------------------------------------------------------------------------
# Registrars
# ---------------------------------------------------------------------------


# ``ModelT`` / ``SchemaT`` link the four contractually-related arguments
# — model class, detail queryset, serializer, response schema must agree.
def register_entity_delete_restore[ModelT: CatalogModel, SchemaT: Schema](
    router: Router,
    model_cls: type[ModelT],
    *,
    detail_qs: Callable[[], QuerySet[ModelT]],
    serialize_detail: Callable[[ModelT], SchemaT],
    response_schema: type[SchemaT],
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
    public_id_field = model_cls.public_id_field

    def _delete_preview(
        request: HttpRequest, public_id: str
    ) -> TaxonomyDeletePreviewSchema:
        obj = get_object_or_404(
            model_cls.objects.active(), **{public_id_field: public_id}
        )
        plan = plan_soft_delete(obj)

        active_children = 0
        if child_related_name is not None:
            active_children = getattr(obj, child_related_name).active().count()

        is_blocked = plan.is_blocked or active_children > 0
        changeset_count = 0 if is_blocked else count_entity_changesets(obj)

        parent_ref: EntityRef | None = None
        if parent_field is not None:
            parent = getattr(obj, parent_field)
            parent_ref = EntityRef(name=parent.name, slug=parent.slug)

        return TaxonomyDeletePreviewSchema(
            name=obj.name,
            slug=obj.slug,
            parent=parent_ref,
            changeset_count=changeset_count,
            blocked_by=[serialize_blocking_referrer(b) for b in plan.blockers],
            active_children_count=active_children,
        )

    _delete_preview.__name__ = f"{entity_label.lower()}_delete_preview"
    router.get(
        "/{path:public_id}/delete-preview/",
        auth=django_auth,
        response=TaxonomyDeletePreviewSchema,
        tags=["private"],
    )(_delete_preview)

    def _delete(
        request: HttpRequest, public_id: str, data: ChangeSetInputSchema
    ) -> DeleteResponseSchema | Status[SoftDeleteBlockedSchema | AlreadyDeletedSchema]:
        check_and_record(request.user, DELETE_RATE_LIMIT_SPEC)

        obj = get_object_or_404(
            model_cls.objects.active(), **{public_id_field: public_id}
        )

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
                    SoftDeleteBlockedSchema(
                        detail=(
                            f"Cannot delete: {obj.name} has {active_children} "
                            f"active child"
                            f"{'ren' if active_children != 1 else ''}. "
                            "Delete those first."
                        ),
                        blocked_by=[],
                        active_children_count=active_children,
                    ),
                )

        try:
            changeset, deleted = execute_soft_delete(
                obj, user=request.user, note=data.note, citation=data.citation
            )
        except SoftDeleteBlockedError as exc:
            return Status(
                422,
                SoftDeleteBlockedSchema(
                    detail=("Cannot delete: active references would be left dangling."),
                    blocked_by=[serialize_blocking_referrer(b) for b in exc.blockers],
                    active_children_count=0,
                ),
            )

        if changeset is None:
            return Status(
                422,
                AlreadyDeletedSchema(detail=f"{friendly_sentence} is already deleted."),
            )

        return DeleteResponseSchema(
            changeset_id=changeset.pk,
            affected_slugs=[e.slug for e in deleted if isinstance(e, model_cls)],
        )

    _delete.__name__ = f"{entity_label.lower()}_delete"
    router.post(
        "/{path:public_id}/delete/",
        auth=django_auth,
        response={
            200: DeleteResponseSchema,
            422: SoftDeleteBlockedSchema | AlreadyDeletedSchema,
            429: RateLimitErrorSchema,
        },
        tags=["private"],
    )(_delete)

    def _restore(
        request: HttpRequest, public_id: str, data: ChangeSetInputSchema
    ) -> SchemaT | Status[ErrorDetailSchema]:
        check_and_record(request.user, CREATE_RATE_LIMIT_SPEC)

        # Bypass .active() — we're looking for soft-deleted rows.
        obj = get_object_or_404(model_cls, **{public_id_field: public_id})
        if obj.status != "deleted":
            return Status(
                422, ErrorDetailSchema(detail=f"{friendly_sentence} is not deleted.")
            )

        if parent_field is not None:
            parent = getattr(obj, parent_field)
            if parent.status == "deleted":
                return Status(
                    422, ErrorDetailSchema(detail=f"Restore {parent.name} first.")
                )

        execute_claims(
            obj,
            [ClaimSpec(field_name="status", value="active")],
            user=request.user,
            action=ChangeSetAction.EDIT,
            note=data.note,
            citation=data.citation,
        )

        refreshed = get_object_or_404(detail_qs(), **{public_id_field: public_id})
        return serialize_detail(refreshed)

    _restore.__name__ = f"{entity_label.lower()}_restore"
    router.post(
        "/{path:public_id}/restore/",
        auth=django_auth,
        response={
            200: response_schema,
            422: ErrorDetailSchema,
            404: ErrorDetailSchema,
            429: RateLimitErrorSchema,
        },
        tags=["private"],
    )(_restore)


def register_entity_create[ModelT: CatalogModel, SchemaT: Schema](
    router: Router,
    model_cls: type[ModelT],
    *,
    detail_qs: Callable[[], QuerySet[ModelT]],
    serialize_detail: Callable[[ModelT], SchemaT],
    response_schema: type[SchemaT],
    parent_field: str | None = None,
    parent_model: type[CatalogModel] | None = None,
    route_suffix: str = "",
    scope_filter_builder: Callable[[Any], Q] | None = None,
    include_deleted_name_check: bool = False,
) -> None:
    """Attach a POST create route.

    When *parent_field* is None, mounts ``POST /`` on the entity's own
    router. Otherwise all three parent-related args must be supplied
    together and the route mounts at
    ``POST /{path:parent_public_id}/<route_suffix>/`` on the *parent's*
    router — mirroring the Title → Model nesting.

    FK claim values come from ``model_cls.claim_fk_lookups`` (defaults to
    the parent's ``slug`` when unset; Location overrides ``parent`` to
    ``location_path``). Hardcoding ``parent.slug`` anywhere on the write
    path is a field-on-model antipattern.

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
    # django-stubs returns ``Any`` for ``_meta.get_field`` on a TypeVar'd
    # model; the assert is the runtime narrowing to ``Field``.
    name_field = model_cls._meta.get_field("name")
    assert isinstance(name_field, db_models.Field)
    name_max = name_field.max_length
    assert name_max is not None
    friendly = model_cls.entity_type.replace("-", " ")
    parent_lookup_field: str | None = None
    if parent_field is not None and parent_model is not None:
        parent_lookup_field = parent_model.public_id_field

    def _do_create(
        request: HttpRequest,
        data: EntityCreateInputSchema,
        parent: CatalogModel | None = None,
    ) -> Status[Any]:
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

        row_kwargs: dict[str, Any] = {"name": name, "slug": slug, "status": "active"}
        claim_specs = [
            ClaimSpec(field_name="name", value=name),
            ClaimSpec(field_name="slug", value=slug),
            ClaimSpec(field_name="status", value="active"),
        ]
        if parent is not None:
            assert parent_field is not None
            row_kwargs[parent_field] = parent
            # FK claim value reads from claim_fk_lookups (defaults to parent's
            # slug); models with multi-segment URL identity (e.g. Location)
            # override to the parent's path-encoded field.
            fk_lookup = model_cls.claim_fk_lookups.get(parent_field, "slug")
            claim_specs.append(
                ClaimSpec(field_name=parent_field, value=getattr(parent, fk_lookup))
            )

        entity = create_entity_with_claims(
            model_cls,
            row_kwargs=row_kwargs,
            claim_specs=claim_specs,
            user=request.user,
            note=data.note,
            citation=data.citation,
        )

        # Refetch via the prefetch-rich ``detail_qs`` for serialization.
        # Use pk (not public_id_field) — the freshly inserted row's pk is
        # the most reliable handle and does not depend on whether
        # ``public_id_field`` was populated synchronously by
        # ``model_cls.objects.create``.
        created = get_object_or_404(detail_qs(), pk=entity.pk)
        return Status(201, serialize_detail(created))

    if parented:
        assert parent_model is not None
        assert parent_lookup_field is not None

        def _create_parented(
            request: HttpRequest,
            parent_public_id: str,
            data: EntityCreateInputSchema,
        ) -> Status[Any]:
            parent = get_object_or_404(
                parent_model.objects.active(),
                **{parent_lookup_field: parent_public_id},
            )
            return _do_create(request, data, parent=parent)

        _create_parented.__name__ = f"{entity_label.lower()}_create"
        router.post(
            f"/{{path:parent_public_id}}/{route_suffix}/",
            auth=django_auth,
            response={
                201: response_schema,
                422: ValidationErrorSchema,
                429: RateLimitErrorSchema,
            },
            tags=["private"],
        )(_create_parented)
    else:

        def _create_unparented(
            request: HttpRequest, data: EntityCreateInputSchema
        ) -> Status[Any]:
            return _do_create(request, data)

        _create_unparented.__name__ = f"{entity_label.lower()}_create"
        router.post(
            "/",
            auth=django_auth,
            response={
                201: response_schema,
                422: ValidationErrorSchema,
                429: RateLimitErrorSchema,
            },
            tags=["private"],
        )(_create_unparented)
