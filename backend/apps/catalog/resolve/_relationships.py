"""Resolution logic for relationship claims (credits, themes, gameplay features, tags,
abbreviations).

Includes both single-object and bulk variants for each relationship type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db.models import Case, F, IntegerField, Value, When

from apps.provenance.models import Claim

from ..models import (
    Credit,
    CreditRole,
    GameplayFeature,
    MachineModel,
    ModelAbbreviation,
    Person,
    Tag,
    Theme,
    Title,
    TitleAbbreviation,
)
from ._helpers import _pick_relationship_winners

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# M2M relationship registry
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class M2MFieldSpec:
    """Descriptor for a simple M2M relationship resolved from claims."""

    field_name: str  # claim field_name: "theme", "tag", "gameplay_feature"
    slug_key: str  # key in claim value dict: "theme_slug", "tag_slug", etc.
    m2m_attr: str  # model attribute: "themes", "tags", "gameplay_features"
    target_model: type  # Theme, Tag, GameplayFeature


M2M_FIELDS: dict[str, M2MFieldSpec] = {
    "theme": M2MFieldSpec("theme", "theme_slug", "themes", Theme),
    "gameplay_feature": M2MFieldSpec(
        "gameplay_feature",
        "gameplay_feature_slug",
        "gameplay_features",
        GameplayFeature,
    ),
    "tag": M2MFieldSpec("tag", "tag_slug", "tags", Tag),
}


# ------------------------------------------------------------------
# Generic M2M resolvers
# ------------------------------------------------------------------


def _resolve_m2m_single(obj, spec: M2MFieldSpec) -> None:
    """Resolve M2M claims for a single object using the given spec."""
    winners = _pick_relationship_winners(obj, spec.field_name)

    desired_pks: set[int] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        target = spec.target_model.objects.filter(slug=val[spec.slug_key]).first()
        if not target:
            logger.warning(
                "Unresolved %s slug %r in %s claim for %s",
                spec.field_name,
                val[spec.slug_key],
                spec.field_name,
                obj,
            )
            continue
        desired_pks.add(target.pk)

    getattr(obj, spec.m2m_attr).set(desired_pks)


def _resolve_all_m2m(
    spec: M2MFieldSpec,
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve M2M claims into through-table rows for the given spec."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch slug→pk lookup.
    slug_lookup: dict[str, int] = dict(
        spec.target_model.objects.values_list("slug", "pk")
    )

    # Pre-fetch active claims with priority annotation.
    claims_qs = Claim.objects.filter(
        is_active=True, content_type=ct, field_name=spec.field_name
    )
    if model_ids is not None:
        claims_qs = claims_qs.filter(object_id__in=model_ids)
    claims = (
        claims_qs.select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("object_id", "claim_key", "-effective_priority", "-created_at")
    )

    # Pick winner per (object_id, claim_key).
    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired PKs from winning claims.
    desired_by_model: dict[int, set[int]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[int] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            target_pk = slug_lookup.get(val[spec.slug_key])
            if target_pk is None:
                logger.warning(
                    "Unresolved %s slug %r in claim (model pk=%s)",
                    spec.field_name,
                    val[spec.slug_key],
                    model_id,
                )
                continue
            desired.add(target_pk)
        desired_by_model[model_id] = desired

    # Pre-fetch existing M2M through-table rows.
    all_model_ids = model_ids if model_ids is not None else {pm.pk for pm in all_models}
    through = getattr(MachineModel, spec.m2m_attr).through
    target_col = spec.target_model._meta.model_name + "_id"

    existing_by_model: dict[int, set[int]] = {}
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "machinemodel_id", target_col
    ):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply.
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for target_pk in desired - existing:
            to_create.append(
                through(machinemodel_id=model_id, **{target_col: target_pk})
            )

    # Build a lookup for deletions.
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "pk", "machinemodel_id", target_col
    ):
        pk, model_id, fk_id = row
        desired = desired_by_model.get(model_id, set())
        if fk_id not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        through.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        through.objects.bulk_create(to_create, batch_size=2000)


# ------------------------------------------------------------------
# Public M2M wrappers (single-object)
# ------------------------------------------------------------------


def resolve_themes(machine_model: MachineModel) -> None:
    _resolve_m2m_single(machine_model, M2M_FIELDS["theme"])


def resolve_gameplay_features(machine_model: MachineModel) -> None:
    _resolve_m2m_single(machine_model, M2M_FIELDS["gameplay_feature"])


def resolve_tags(machine_model: MachineModel) -> None:
    _resolve_m2m_single(machine_model, M2M_FIELDS["tag"])


# ------------------------------------------------------------------
# Public M2M wrappers (bulk)
# ------------------------------------------------------------------


def resolve_all_themes(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    _resolve_all_m2m(M2M_FIELDS["theme"], all_models, model_ids=model_ids)


def resolve_all_gameplay_features(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    _resolve_all_m2m(M2M_FIELDS["gameplay_feature"], all_models, model_ids=model_ids)


def resolve_all_tags(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    _resolve_all_m2m(M2M_FIELDS["tag"], all_models, model_ids=model_ids)


# ------------------------------------------------------------------
# Credits (compound identity — not amenable to generic M2M)
# ------------------------------------------------------------------


def resolve_credits(machine_model: MachineModel) -> None:
    """Resolve credit claims into Credit rows for a single machine."""
    winners = _pick_relationship_winners(machine_model, "credit")

    role_lookup: dict[str, int] = dict(CreditRole.objects.values_list("slug", "pk"))
    if not role_lookup:
        if winners:
            logger.warning(
                "CreditRole table is empty — skipping credit resolution for %s. "
                "Run ingest_pinbase_taxonomy to seed credit roles.",
                machine_model.name,
            )
        return

    desired: set[tuple[int, int]] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        person = Person.objects.filter(slug=val["person_slug"]).first()
        if not person:
            logger.warning(
                "Unresolved person slug %r in credit claim for %s",
                val["person_slug"],
                machine_model.name,
            )
            continue
        role_id = role_lookup.get(val["role"])
        if role_id is None:
            logger.warning(
                "Unresolved credit role %r in credit claim for %s",
                val["role"],
                machine_model.name,
            )
            continue
        desired.add((person.pk, role_id))

    existing = set(machine_model.credits.values_list("person_id", "role_id"))

    to_create = desired - existing
    to_delete = existing - desired

    if to_delete:
        for person_id, role_id in to_delete:
            machine_model.credits.filter(person_id=person_id, role_id=role_id).delete()

    if to_create:
        Credit.objects.bulk_create(
            [
                Credit(model=machine_model, person_id=person_id, role_id=role_id)
                for person_id, role_id in to_create
            ]
        )


def resolve_all_credits(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve credit claims into Credit rows."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    person_lookup: dict[str, int] = dict(Person.objects.values_list("slug", "pk"))
    role_lookup: dict[str, int] = dict(CreditRole.objects.values_list("slug", "pk"))
    if not role_lookup:
        logger.warning(
            "CreditRole table is empty — skipping bulk credit resolution. "
            "Run ingest_pinbase_taxonomy to seed credit roles."
        )
        return

    credit_qs = Claim.objects.filter(
        is_active=True, content_type=ct, field_name="credit"
    )
    if model_ids is not None:
        credit_qs = credit_qs.filter(object_id__in=model_ids)
    credit_claims = (
        credit_qs.select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("object_id", "claim_key", "-effective_priority", "-created_at")
    )

    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in credit_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    desired_by_model: dict[int, set[tuple[int, int]]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[tuple[int, int]] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            person_pk = person_lookup.get(val["person_slug"])
            if person_pk is None:
                logger.warning(
                    "Unresolved person slug %r in credit claim (model pk=%s)",
                    val["person_slug"],
                    model_id,
                )
                continue
            role_pk = role_lookup.get(val["role"])
            if role_pk is None:
                logger.warning(
                    "Unresolved credit role %r in credit claim (model pk=%s)",
                    val["role"],
                    model_id,
                )
                continue
            desired.add((person_pk, role_pk))
        desired_by_model[model_id] = desired

    all_model_ids = model_ids if model_ids is not None else {pm.pk for pm in all_models}
    existing_by_model: dict[int, set[tuple[int, int]]] = {}
    dc_qs = Credit.objects.filter(model_id__in=all_model_ids)
    for dc in dc_qs.values_list("model_id", "person_id", "role_id"):
        existing_by_model.setdefault(dc[0], set()).add((dc[1], dc[2]))

    to_create: list[Credit] = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for person_id, role_id in desired - existing:
            to_create.append(
                Credit(model_id=model_id, person_id=person_id, role_id=role_id)
            )

    for dc in Credit.objects.filter(model_id__in=all_model_ids).values_list(
        "pk", "model_id", "person_id", "role_id"
    ):
        pk, model_id, person_id, role_id = dc
        desired = desired_by_model.get(model_id, set())
        if (person_id, role_id) not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        Credit.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        Credit.objects.bulk_create(to_create, batch_size=2000)


# ------------------------------------------------------------------
# Abbreviation resolvers (string values, dedup logic — not generic M2M)
# ------------------------------------------------------------------


def resolve_title_abbreviations(title: Title) -> None:
    """Resolve abbreviation claims into TitleAbbreviation rows for a single Title."""
    winners = _pick_relationship_winners(title, "abbreviation")

    desired: set[str] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        desired.add(val["value"])

    existing = set(title.abbreviations.values_list("value", flat=True))

    for value in desired - existing:
        TitleAbbreviation.objects.create(title=title, value=value)

    if stale := existing - desired:
        title.abbreviations.filter(value__in=stale).delete()


def resolve_model_abbreviations(machine_model: MachineModel) -> None:
    """Resolve abbreviation claims into ModelAbbreviation rows for a single MachineModel."""
    winners = _pick_relationship_winners(machine_model, "abbreviation")

    desired: set[str] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        desired.add(val["value"])

    # Deduplicate: remove abbreviations that already exist on the title.
    if machine_model.title_id:
        title_abbrs = set(
            TitleAbbreviation.objects.filter(
                title_id=machine_model.title_id
            ).values_list("value", flat=True)
        )
        desired -= title_abbrs

    existing = set(machine_model.abbreviations.values_list("value", flat=True))

    for value in desired - existing:
        ModelAbbreviation.objects.create(machine_model=machine_model, value=value)

    if stale := existing - desired:
        machine_model.abbreviations.filter(value__in=stale).delete()


def resolve_all_title_abbreviations(
    all_titles: list[Title],
    *,
    title_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve abbreviation claims into TitleAbbreviation rows."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(Title)

    abbr_qs = Claim.objects.filter(
        is_active=True, content_type=ct, field_name="abbreviation"
    )
    if title_ids is not None:
        abbr_qs = abbr_qs.filter(object_id__in=title_ids)
    abbr_claims = (
        abbr_qs.select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("object_id", "claim_key", "-effective_priority", "-created_at")
    )

    winners_by_title: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in abbr_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_title.setdefault(claim.object_id, []).append(claim)

    desired_by_title: dict[int, set[str]] = {}
    for title_id, claims_list in winners_by_title.items():
        desired: set[str] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            desired.add(val["value"])
        desired_by_title[title_id] = desired

    all_title_ids = title_ids if title_ids is not None else {t.pk for t in all_titles}
    existing_by_title: dict[int, set[str]] = {}
    for row in TitleAbbreviation.objects.filter(title_id__in=all_title_ids).values_list(
        "title_id", "value"
    ):
        existing_by_title.setdefault(row[0], set()).add(row[1])

    to_create = []
    to_delete_pks: list[int] = []

    for title_id in all_title_ids:
        desired = desired_by_title.get(title_id, set())
        existing = existing_by_title.get(title_id, set())

        for value in desired - existing:
            to_create.append(TitleAbbreviation(title_id=title_id, value=value))

    for row in TitleAbbreviation.objects.filter(title_id__in=all_title_ids).values_list(
        "pk", "title_id", "value"
    ):
        pk, title_id, value = row
        desired = desired_by_title.get(title_id, set())
        if value not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        TitleAbbreviation.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        TitleAbbreviation.objects.bulk_create(to_create, batch_size=2000)


def _get_title_abbrs_for_models(
    model_ids: set[int],
) -> dict[int, set[str]]:
    """Return {model_id: set(abbreviation_values)} from each model's title."""
    model_title_map = dict(
        MachineModel.objects.filter(pk__in=model_ids, title__isnull=False).values_list(
            "pk", "title_id"
        )
    )
    if not model_title_map:
        return {}

    title_ids = set(model_title_map.values())
    title_abbrs: dict[int, set[str]] = {}
    for title_id, value in TitleAbbreviation.objects.filter(
        title_id__in=title_ids
    ).values_list("title_id", "value"):
        title_abbrs.setdefault(title_id, set()).add(value)

    result: dict[int, set[str]] = {}
    for model_id, title_id in model_title_map.items():
        abbrs = title_abbrs.get(title_id)
        if abbrs:
            result[model_id] = abbrs
    return result


def resolve_all_model_abbreviations(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve abbreviation claims into ModelAbbreviation rows."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    abbr_qs = Claim.objects.filter(
        is_active=True, content_type=ct, field_name="abbreviation"
    )
    if model_ids is not None:
        abbr_qs = abbr_qs.filter(object_id__in=model_ids)
    abbr_claims = (
        abbr_qs.select_related("source", "user__profile")
        .annotate(
            effective_priority=Case(
                When(source__isnull=False, then=F("source__priority")),
                When(user__isnull=False, then=F("user__profile__priority")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("object_id", "claim_key", "-effective_priority", "-created_at")
    )

    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in abbr_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    desired_by_model: dict[int, set[str]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[str] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            desired.add(val["value"])
        desired_by_model[model_id] = desired

    all_model_ids = model_ids if model_ids is not None else {pm.pk for pm in all_models}
    title_abbrs_by_model = _get_title_abbrs_for_models(all_model_ids)
    for model_id in list(desired_by_model):
        title_abbrs = title_abbrs_by_model.get(model_id, set())
        if title_abbrs:
            desired_by_model[model_id] -= title_abbrs

    existing_by_model: dict[int, set[str]] = {}
    for row in ModelAbbreviation.objects.filter(
        machine_model_id__in=all_model_ids
    ).values_list("machine_model_id", "value"):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for value in desired - existing:
            to_create.append(ModelAbbreviation(machine_model_id=model_id, value=value))

    for row in ModelAbbreviation.objects.filter(
        machine_model_id__in=all_model_ids
    ).values_list("pk", "machine_model_id", "value"):
        pk, model_id, value = row
        desired = desired_by_model.get(model_id, set())
        if value not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        ModelAbbreviation.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        ModelAbbreviation.objects.bulk_create(to_create, batch_size=2000)
