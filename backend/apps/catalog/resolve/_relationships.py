"""Resolution logic for relationship claims (credits, themes, gameplay features, tags,
abbreviations).

Includes both single-object and bulk variants for each relationship type.
"""

from __future__ import annotations

import logging

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
# Single-object relationship resolvers
# ------------------------------------------------------------------


def resolve_credits(machine_model: MachineModel) -> None:
    """Resolve credit claims into Credit rows for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the Person by slug and materializes a Credit.
    """
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

    # Desired credits from winning claims.
    desired: set[tuple[int, int]] = set()  # (person_id, role_id)
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

    # Existing credits.
    existing = set(machine_model.credits.values_list("person_id", "role_id"))

    # Diff and apply.
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


def resolve_themes(machine_model: MachineModel) -> None:
    """Resolve theme claims into the M2M for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the Theme by slug and sets the M2M.
    """
    winners = _pick_relationship_winners(machine_model, "theme")

    desired_pks: set[int] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        theme = Theme.objects.filter(slug=val["theme_slug"]).first()
        if not theme:
            logger.warning(
                "Unresolved theme slug %r in theme claim for %s",
                val["theme_slug"],
                machine_model.name,
            )
            continue
        desired_pks.add(theme.pk)

    machine_model.themes.set(desired_pks)


def resolve_gameplay_features(machine_model: MachineModel) -> None:
    """Resolve gameplay feature claims into the M2M for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the GameplayFeature by slug and sets the M2M.
    """
    winners = _pick_relationship_winners(machine_model, "gameplay_feature")

    desired_pks: set[int] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        feature = GameplayFeature.objects.filter(
            slug=val["gameplay_feature_slug"]
        ).first()
        if not feature:
            logger.warning(
                "Unresolved gameplay feature slug %r in claim for %s",
                val["gameplay_feature_slug"],
                machine_model.name,
            )
            continue
        desired_pks.add(feature.pk)

    machine_model.gameplay_features.set(desired_pks)


def resolve_tags(machine_model: MachineModel) -> None:
    """Resolve tag claims into the M2M for a single machine.

    Picks the winning claim per claim_key. Where ``value["exists"]`` is
    True, looks up the Tag by slug and sets the M2M.
    """
    winners = _pick_relationship_winners(machine_model, "tag")

    desired_pks: set[int] = set()
    for claim in winners.values():
        val = claim.value
        if not val.get("exists", True):
            continue
        tag = Tag.objects.filter(slug=val["tag_slug"]).first()
        if not tag:
            logger.warning(
                "Unresolved tag slug %r in tag claim for %s",
                val["tag_slug"],
                machine_model.name,
            )
            continue
        desired_pks.add(tag.pk)

    machine_model.tags.set(desired_pks)


# ------------------------------------------------------------------
# Bulk relationship resolvers
# ------------------------------------------------------------------


def resolve_all_credits(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve credit claims into Credit rows.

    If *model_ids* is given, only claims and rows for those models are
    queried.  Otherwise all models in *all_models* are processed.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch person slug→pk and role slug→pk lookups.
    person_lookup: dict[str, int] = dict(Person.objects.values_list("slug", "pk"))
    role_lookup: dict[str, int] = dict(CreditRole.objects.values_list("slug", "pk"))
    if not role_lookup:
        logger.warning(
            "CreditRole table is empty — skipping bulk credit resolution. "
            "Run ingest_pinbase_taxonomy to seed credit roles."
        )
        return

    # Pre-fetch active credit claims with priority annotation.
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

    # Pick winner per (object_id, claim_key).
    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in credit_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired credits from winning claims.
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

    # Pre-fetch existing Credit rows (model-linked only, not series credits).
    all_model_ids = model_ids if model_ids is not None else {pm.pk for pm in all_models}
    existing_by_model: dict[int, set[tuple[int, int]]] = {}
    dc_qs = Credit.objects.filter(model_id__in=all_model_ids)
    for dc in dc_qs.values_list("model_id", "person_id", "role_id"):
        existing_by_model.setdefault(dc[0], set()).add((dc[1], dc[2]))

    # Diff and apply.
    to_create: list[Credit] = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for person_id, role_id in desired - existing:
            to_create.append(
                Credit(model_id=model_id, person_id=person_id, role_id=role_id)
            )

    # Build a lookup for deletions.
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


def resolve_all_themes(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve theme claims into M2M rows.

    If *model_ids* is given, only claims and rows for those models are
    queried.  Otherwise all models in *all_models* are processed.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch theme slug→pk lookup.
    theme_lookup: dict[str, int] = dict(Theme.objects.values_list("slug", "pk"))

    # Pre-fetch active theme claims with priority annotation.
    theme_qs = Claim.objects.filter(is_active=True, content_type=ct, field_name="theme")
    if model_ids is not None:
        theme_qs = theme_qs.filter(object_id__in=model_ids)
    theme_claims = (
        theme_qs.select_related("source", "user__profile")
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
    for claim in theme_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired themes from winning claims.
    desired_by_model: dict[int, set[int]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[int] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            theme_pk = theme_lookup.get(val["theme_slug"])
            if theme_pk is None:
                logger.warning(
                    "Unresolved theme slug %r in theme claim (model pk=%s)",
                    val["theme_slug"],
                    model_id,
                )
                continue
            desired.add(theme_pk)
        desired_by_model[model_id] = desired

    # Pre-fetch existing M2M through-table rows.
    all_model_ids = model_ids if model_ids is not None else {pm.pk for pm in all_models}
    through = MachineModel.themes.through
    existing_by_model: dict[int, set[int]] = {}
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "machinemodel_id", "theme_id"
    ):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply.
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for theme_pk in desired - existing:
            to_create.append(through(machinemodel_id=model_id, theme_id=theme_pk))

    # Build a lookup for deletions.
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "pk", "machinemodel_id", "theme_id"
    ):
        pk, model_id, theme_id = row
        desired = desired_by_model.get(model_id, set())
        if theme_id not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        through.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        through.objects.bulk_create(to_create, batch_size=2000)


def _resolve_all_gameplay_features(all_models: list[MachineModel]) -> None:
    """Bulk-resolve gameplay feature claims into M2M rows for all models.

    Follows the same pattern as ``resolve_all_themes()``.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch gameplay feature slug→pk lookup.
    feature_lookup: dict[str, int] = dict(
        GameplayFeature.objects.values_list("slug", "pk")
    )

    # Pre-fetch all active gameplay feature claims with priority annotation.
    feature_claims = (
        Claim.objects.filter(
            is_active=True, content_type=ct, field_name="gameplay_feature"
        )
        .select_related("source", "user__profile")
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
    for claim in feature_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired features from winning claims.
    desired_by_model: dict[int, set[int]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[int] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            feature_pk = feature_lookup.get(val["gameplay_feature_slug"])
            if feature_pk is None:
                logger.warning(
                    "Unresolved gameplay feature slug %r in claim (model pk=%s)",
                    val["gameplay_feature_slug"],
                    model_id,
                )
                continue
            desired.add(feature_pk)
        desired_by_model[model_id] = desired

    # Pre-fetch existing M2M through-table rows.
    through = MachineModel.gameplay_features.through
    existing_by_model: dict[int, set[int]] = {}
    for row in through.objects.values_list("machinemodel_id", "gameplayfeature_id"):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply for ALL models.
    all_model_ids = {pm.pk for pm in all_models}
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for feature_pk in desired - existing:
            to_create.append(
                through(machinemodel_id=model_id, gameplayfeature_id=feature_pk)
            )

    # Build a lookup for deletions.
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "pk", "machinemodel_id", "gameplayfeature_id"
    ):
        pk, model_id, feature_id = row
        desired = desired_by_model.get(model_id, set())
        if feature_id not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        through.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        through.objects.bulk_create(to_create, batch_size=2000)


def _resolve_all_tags(all_models: list[MachineModel]) -> None:
    """Bulk-resolve tag claims into M2M rows for all models.

    Follows the same pattern as ``resolve_all_themes()``.
    """
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch tag slug→pk lookup.
    tag_lookup: dict[str, int] = dict(Tag.objects.values_list("slug", "pk"))

    # Pre-fetch all active tag claims with priority annotation.
    tag_claims = (
        Claim.objects.filter(is_active=True, content_type=ct, field_name="tag")
        .select_related("source", "user__profile")
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
    for claim in tag_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired tags from winning claims.
    desired_by_model: dict[int, set[int]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[int] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            tag_pk = tag_lookup.get(val["tag_slug"])
            if tag_pk is None:
                logger.warning(
                    "Unresolved tag slug %r in tag claim (model pk=%s)",
                    val["tag_slug"],
                    model_id,
                )
                continue
            desired.add(tag_pk)
        desired_by_model[model_id] = desired

    # Pre-fetch existing M2M through-table rows.
    through = MachineModel.tags.through
    existing_by_model: dict[int, set[int]] = {}
    for row in through.objects.values_list("machinemodel_id", "tag_id"):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply for ALL models.
    all_model_ids = {pm.pk for pm in all_models}
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for tag_pk in desired - existing:
            to_create.append(through(machinemodel_id=model_id, tag_id=tag_pk))

    # Build a lookup for deletions.
    for row in through.objects.filter(machinemodel_id__in=all_model_ids).values_list(
        "pk", "machinemodel_id", "tag_id"
    ):
        pk, model_id, tag_id = row
        desired = desired_by_model.get(model_id, set())
        if tag_id not in desired:
            to_delete_pks.append(pk)

    if to_delete_pks:
        through.objects.filter(pk__in=to_delete_pks).delete()
    if to_create:
        through.objects.bulk_create(to_create, batch_size=2000)


# ------------------------------------------------------------------
# Single-object abbreviation resolvers
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

    # Create new abbreviations.
    for value in desired - existing:
        TitleAbbreviation.objects.create(title=title, value=value)

    # Remove stale abbreviations.
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

    existing = set(machine_model.abbreviations.values_list("value", flat=True))

    for value in desired - existing:
        ModelAbbreviation.objects.create(machine_model=machine_model, value=value)

    if stale := existing - desired:
        machine_model.abbreviations.filter(value__in=stale).delete()


# ------------------------------------------------------------------
# Bulk abbreviation resolvers
# ------------------------------------------------------------------


def resolve_all_title_abbreviations(
    all_titles: list[Title],
    *,
    title_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve abbreviation claims into TitleAbbreviation rows."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(Title)

    # Pre-fetch active abbreviation claims with priority annotation.
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

    # Pick winner per (object_id, claim_key).
    winners_by_title: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in abbr_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_title.setdefault(claim.object_id, []).append(claim)

    # Desired abbreviation values from winning claims.
    desired_by_title: dict[int, set[str]] = {}
    for title_id, claims_list in winners_by_title.items():
        desired: set[str] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            desired.add(val["value"])
        desired_by_title[title_id] = desired

    # Pre-fetch existing TitleAbbreviation rows.
    all_title_ids = title_ids if title_ids is not None else {t.pk for t in all_titles}
    existing_by_title: dict[int, set[str]] = {}
    for row in TitleAbbreviation.objects.filter(title_id__in=all_title_ids).values_list(
        "title_id", "value"
    ):
        existing_by_title.setdefault(row[0], set()).add(row[1])

    # Diff and apply.
    to_create = []
    to_delete_pks: list[int] = []

    for title_id in all_title_ids:
        desired = desired_by_title.get(title_id, set())
        existing = existing_by_title.get(title_id, set())

        for value in desired - existing:
            to_create.append(TitleAbbreviation(title_id=title_id, value=value))

    # Build a lookup for deletions.
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


def resolve_all_model_abbreviations(
    all_models: list[MachineModel],
    *,
    model_ids: set[int] | None = None,
) -> None:
    """Bulk-resolve abbreviation claims into ModelAbbreviation rows."""
    from django.contrib.contenttypes.models import ContentType

    ct = ContentType.objects.get_for_model(MachineModel)

    # Pre-fetch active abbreviation claims with priority annotation.
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

    # Pick winner per (object_id, claim_key).
    winners_by_model: dict[int, list[Claim]] = {}
    seen: set[tuple[int, str]] = set()
    for claim in abbr_claims:
        key = (claim.object_id, claim.claim_key)
        if key not in seen:
            seen.add(key)
            winners_by_model.setdefault(claim.object_id, []).append(claim)

    # Desired abbreviation values from winning claims.
    desired_by_model: dict[int, set[str]] = {}
    for model_id, claims_list in winners_by_model.items():
        desired: set[str] = set()
        for claim in claims_list:
            val = claim.value
            if not val.get("exists", True):
                continue
            desired.add(val["value"])
        desired_by_model[model_id] = desired

    # Pre-fetch existing ModelAbbreviation rows.
    all_model_ids = model_ids if model_ids is not None else {pm.pk for pm in all_models}
    existing_by_model: dict[int, set[str]] = {}
    for row in ModelAbbreviation.objects.filter(
        machine_model_id__in=all_model_ids
    ).values_list("machine_model_id", "value"):
        existing_by_model.setdefault(row[0], set()).add(row[1])

    # Diff and apply.
    to_create = []
    to_delete_pks: list[int] = []

    for model_id in all_model_ids:
        desired = desired_by_model.get(model_id, set())
        existing = existing_by_model.get(model_id, set())

        for value in desired - existing:
            to_create.append(ModelAbbreviation(machine_model_id=model_id, value=value))

    # Build a lookup for deletions.
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
