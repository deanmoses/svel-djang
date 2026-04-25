"""Claim model and manager: atomic fact assertions about catalog entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, NamedTuple

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models.functions import Now

from apps.core.models import field_not_blank
from apps.core.types import ClaimIdentity

from .base import ClaimControlledModel
from .changeset import ChangeSet
from .source import Source

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from apps.core.models import License

    from .citation_instance import CitationInstance

type IdentityPart = str | int | None
"""One value in a claim_key's identity-parts mapping: an entity-reference PK
(``int``), a literal key like an alias value (``str``), or ``None``
(serialized as the literal ``"null"`` in the key)."""


class ExistingClaimRow(NamedTuple):
    """Partial Claim row cached during claim diffing.

    Fetched via ``values_list`` to avoid JSONField deserialization cost on
    large sources. Field order matches the ``values_list`` column order.
    """

    # ``value`` is the raw JSONField payload — scalar, dict, list, or null.
    value: object
    citation: str
    needs_review: bool
    needs_review_notes: str
    license_id: int | None
    pk: int


def _escape_claim_value(s: str) -> str:
    """Percent-escape reserved delimiters in claim key identity values."""
    return s.replace("%", "%25").replace("|", "%7C").replace(":", "%3A")


def make_claim_key(field_name: str, **identity_parts: IdentityPart) -> str:
    """Build a canonical claim_key from field_name and sorted identity parts.

    For scalar claims, call with just field_name (returns field_name unchanged).
    For relationship claims, pass identity parts as keyword arguments.

    Reserved characters (``|`` and ``:``) in identity values are
    percent-escaped so the key remains unambiguous.
    """
    if not identity_parts:
        return field_name
    parts = [field_name]
    for k in sorted(identity_parts):
        v = identity_parts[k]
        s = "null" if v is None else str(v)
        parts.append(f"{k}:{_escape_claim_value(s)}")
    return "|".join(parts)


class ClaimManager(models.Manager["Claim"]):
    def assert_claim(
        self,
        subject: ClaimControlledModel,
        field_name: str,
        value: object,
        citation: str = "",
        *,
        source: Source | None = None,
        user: User | None = None,
        claim_key: str = "",
        license: License | None = None,
        changeset: ChangeSet | None = None,
    ) -> Claim:
        """Create a claim, deactivating any existing active claim for the same claim_key+author.

        ``subject`` can be any model instance (MachineModel, Manufacturer, Person, …).
        Exactly one of ``source`` or ``user`` must be provided.
        ``claim_key`` defaults to ``field_name`` for scalar claims.
        ``license`` is an optional per-claim License override (null inherits from source).
        ``changeset`` is an optional ChangeSet to group this claim with others.
        Runs in a transaction to ensure the old claim is deactivated atomically.
        """
        if (source is None) == (user is None):
            raise ValueError("Exactly one of source or user must be provided.")
        if changeset is not None:
            if (
                user is not None
                and changeset.user is not None
                and changeset.user.pk != user.pk
            ):
                raise ValueError("ChangeSet user must match the claim user.")
            ingest_run = changeset.ingest_run
            if source is not None and (
                ingest_run is None or ingest_run.source.pk != source.pk
            ):
                raise ValueError(
                    "ChangeSet must belong to an IngestRun from the same source."
                )
        if not claim_key:
            claim_key = field_name

        # Classify and validate. DIRECT claims get scalar/FK validation.
        # RELATIONSHIP claims get shape validation. EXTRA claims pass through.
        # UNRECOGNIZED claims are rejected outright.
        from apps.provenance.validation import (
            DIRECT,
            RELATIONSHIP,
            UNRECOGNIZED,
            classify_claim,
            validate_claim_value,
            validate_single_relationship_claim,
        )

        model_class = type(subject)
        ct_result = classify_claim(model_class, field_name, claim_key, value)
        if ct_result == UNRECOGNIZED:
            raise ValueError(
                f"Unrecognized claim field_name {field_name!r} on {model_class.__name__}"
            )
        if ct_result == DIRECT:
            value = validate_claim_value(field_name, value, model_class)
        elif ct_result == RELATIONSHIP:
            validate_single_relationship_claim(
                subject_model=model_class,
                field_name=field_name,
                claim_key=claim_key,
                value=value,
            )

        ct = ContentType.objects.get_for_model(subject)
        with transaction.atomic():
            self.filter(
                content_type=ct,
                object_id=subject.pk,
                source=source,
                user=user,
                claim_key=claim_key,
                is_active=True,
            ).update(is_active=False)

            return self.create(
                content_type=ct,
                object_id=subject.pk,
                source=source,
                user=user,
                field_name=field_name,
                claim_key=claim_key,
                value=value,
                citation=citation,
                license=license,
                changeset=changeset,
            )

    def bulk_assert_claims(
        self,
        source: Source,
        pending_claims: list[Claim],
        *,
        sweep_field: str | list[str] = "",
        authoritative_scope: set[tuple[int, int]] | None = None,
    ) -> dict[str, int]:
        """Bulk-assert claims for a source. Only writes what changed.

        Compares pending claims against existing active claims from the same
        source. Unchanged claims are skipped, changed claims are superseded
        (deactivated), and new/changed claims are created in bulk.

        Idempotent: running the same ingest twice writes zero rows the second time.

        ``pending_claims`` is a list of **unsaved** Claim objects with
        ``content_type_id``, ``object_id``, ``field_name``, ``claim_key``,
        ``value``, and ``citation`` set. The ``source`` FK is set here.

        If ``sweep_field`` is provided (a single field name or a list), any
        active claims from this source with one of those field_names that are
        *not* in ``pending_claims`` will be deactivated.
        ``authoritative_scope`` is a set of ``(content_type_id, object_id)``
        tuples defining the full set of entities this source is authoritative
        for. If omitted, scope is derived from pending claims.

        **Full-sync contract**: sweep assumes a full sync — authoritative_scope
        must cover every entity this source is authoritative for, not just a
        partial batch. Omit sweep_field for incremental ingests.
        """
        # 0. Validate claim values (scalars, FK targets, field name recognition).
        from apps.provenance.validation import validate_claims_batch

        pending_claims, validation_rejected = validate_claims_batch(pending_claims)

        # 1. Deduplicate: last-write-wins per (content_type_id, object_id, claim_key),
        #    matching assert_claim() semantics where later calls overwrite.
        seen: dict[ClaimIdentity, Claim] = {}
        for claim in pending_claims:
            claim.source = source
            if not claim.claim_key:
                claim.claim_key = claim.field_name
            seen[
                ClaimIdentity(claim.content_type_id, claim.object_id, claim.claim_key)
            ] = claim
        deduped = list(seen.values())
        duplicates_removed = len(pending_claims) - len(deduped)

        # 2. Fetch existing active claims from this source.
        # Use values_list to avoid full ORM object instantiation — on large
        # sources (40-50k+ claims) the overhead of JSONField deserialization
        # on full Claim objects causes multi-minute stalls on SQLite.
        existing: dict[ClaimIdentity, ExistingClaimRow] = {}
        for row in self.filter(source=source, is_active=True).values_list(
            "pk",
            "content_type_id",
            "object_id",
            "claim_key",
            "value",
            "citation",
            "needs_review",
            "needs_review_notes",
            "license_id",
        ):
            pk, ct_id, obj_id, ck, val, cit, nr, nrn, lic_id = row
            existing[ClaimIdentity(ct_id, obj_id, ck)] = ExistingClaimRow(
                value=val,
                citation=cit,
                needs_review=nr,
                needs_review_notes=nrn,
                license_id=lic_id,
                pk=pk,
            )

        # 3. Diff: skip unchanged, collect superseded + new.
        to_deactivate_ids: list[int] = []
        to_create: list[Claim] = []
        for new_claim in deduped:
            key = ClaimIdentity(
                new_claim.content_type_id, new_claim.object_id, new_claim.claim_key
            )
            old = existing.get(key)
            if old:
                if (
                    old.value == new_claim.value
                    and old.citation == new_claim.citation
                    and old.needs_review == new_claim.needs_review
                    and old.needs_review_notes == new_claim.needs_review_notes
                    and old.license_id == new_claim.license_id
                ):
                    continue  # Already correct
                to_deactivate_ids.append(old.pk)
            to_create.append(new_claim)

        # 4. Sweep: deactivate stale relationship claims not in pending set.
        swept = 0
        if sweep_field:
            sweep_fields = (
                [sweep_field] if isinstance(sweep_field, str) else list(sweep_field)
            )
            pending_keys: set[ClaimIdentity] = {
                ClaimIdentity(c.content_type_id, c.object_id, c.claim_key)
                for c in deduped
            }
            if authoritative_scope:
                parent_groups: dict[int, set[int]] = {}
                for ct_id, obj_id in authoritative_scope:
                    parent_groups.setdefault(ct_id, set()).add(obj_id)
            else:
                parent_groups = {}
                for c in deduped:
                    parent_groups.setdefault(c.content_type_id, set()).add(c.object_id)

            stale_ids: list[int] = []
            for ct_id, obj_ids in parent_groups.items():
                for pk, c_ct_id, c_obj_id, c_ck in self.filter(
                    source=source,
                    field_name__in=sweep_fields,
                    is_active=True,
                    content_type_id=ct_id,
                    object_id__in=obj_ids,
                ).values_list("pk", "content_type_id", "object_id", "claim_key"):
                    if ClaimIdentity(c_ct_id, c_obj_id, c_ck) not in pending_keys:
                        stale_ids.append(pk)

            to_deactivate_ids.extend(stale_ids)
            swept = len(stale_ids)

        # 5. Apply delta atomically.
        with transaction.atomic():
            if to_deactivate_ids:
                self.filter(pk__in=to_deactivate_ids).update(is_active=False)
            if to_create:
                self.bulk_create(to_create, batch_size=2000)

        return {
            "unchanged": len(deduped) - len(to_create),
            "created": len(to_create),
            "superseded": len(to_deactivate_ids) - swept,
            "swept": swept,
            "duplicates_removed": duplicates_removed,
            "validation_rejected": validation_rejected,
        }


class Claim(models.Model):
    """A single fact asserted by a Source or User about any catalog entity.

    Uses a GenericForeignKey (``subject``) so claims can target any model:
    MachineModel, Manufacturer, Person, etc.

    Exactly one of ``source`` or ``user`` must be set — enforced by a
    CheckConstraint and by ClaimManager.assert_claim().
    """

    content_type_id: int
    source_id: int | None
    user_id: int | None
    license_id: int | None
    changeset_id: int | None
    retracted_by_changeset_id: int | None
    citation_instances: models.Manager[CitationInstance]

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    subject = GenericForeignKey("content_type", "object_id")

    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="claims",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="claims",
        null=True,
        blank=True,
    )
    field_name = models.CharField(max_length=255)
    claim_key = models.CharField(
        max_length=255,
        help_text=(
            "Identity key for uniqueness. Equals field_name for scalar claims. "
            "For relationship claims, encodes the relationship identity "
            '(e.g., "credit|person:pat-lawlor|role:art").'
        ),
    )
    changeset = models.ForeignKey(
        ChangeSet,
        on_delete=models.PROTECT,
        related_name="claims",
        null=True,
        blank=True,
        help_text="Optional grouping of claims from a single edit session.",
    )
    retracted_by_changeset = models.ForeignKey(
        ChangeSet,
        on_delete=models.PROTECT,
        related_name="retracted_claims",
        null=True,
        blank=True,
        help_text="The changeset that deactivated this claim (user revert or full_sync retraction).",
    )
    value = models.JSONField()
    citation = models.TextField(blank=True, default="", db_default="")
    license = models.ForeignKey(
        "core.License",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="claims",
        help_text="Per-claim license override. Null inherits from source field license or source default.",
    )
    is_active = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Current assertion from this author for this claim_key on this subject. False = superseded or retracted.",
    )
    needs_review = models.BooleanField(
        default=False,
        db_default=False,
        help_text="Flag for low-confidence claims that need human review.",
    )
    needs_review_notes = models.TextField(
        blank=True,
        default="",
        db_default="",
        help_text="Context for reviewers about why this claim needs attention.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    objects: ClassVar[ClaimManager] = ClaimManager()

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id", "field_name"]),
            models.Index(fields=["content_type", "object_id", "claim_key"]),
            models.Index(fields=["source", "content_type", "object_id"]),
            models.Index(fields=["user", "content_type", "object_id"]),
            models.Index(fields=["field_name", "is_active"]),
            models.Index(fields=["source", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(source__isnull=False, user__isnull=True)
                    | models.Q(source__isnull=True, user__isnull=False)
                ),
                name="provenance_claim_source_xor_user",
            ),
            models.UniqueConstraint(
                fields=["content_type", "object_id", "source", "claim_key"],
                condition=models.Q(is_active=True, source__isnull=False),
                name="provenance_unique_active_claim_per_source",
            ),
            models.UniqueConstraint(
                fields=["content_type", "object_id", "user", "claim_key"],
                condition=models.Q(is_active=True, user__isnull=False),
                name="provenance_unique_active_claim_per_user",
            ),
            field_not_blank("field_name"),
            field_not_blank("claim_key"),
            models.CheckConstraint(
                condition=(
                    models.Q(retracted_by_changeset__isnull=True)
                    | models.Q(is_active=False)
                ),
                name="provenance_claim_retracted_requires_inactive",
                violation_error_message=(
                    "retracted_by_changeset is only allowed when is_active=False."
                ),
                violation_error_code="cross_field",
            ),
        ]

    def __str__(self) -> str:
        if self.source is not None:
            author = self.source.name
        else:
            author = self.user.username if self.user is not None else "unknown"
        return f"{author}: {self.subject}.{self.field_name}"

    @classmethod
    def for_object(
        cls,
        obj: ClaimControlledModel,
        *,
        field_name: str,
        value: object,
        claim_key: str = "",
        **kwargs: object,
    ) -> Claim:
        """Construct an unsaved Claim for a model instance.

        Derives content_type_id from obj automatically, so callers never need
        to capture a ct_id variable. Returns an unsaved instance suitable for
        passing to bulk_assert_claims().
        """
        ct_id = ContentType.objects.get_for_model(obj).pk
        return cls(
            content_type_id=ct_id,
            object_id=obj.pk,
            field_name=field_name,
            claim_key=claim_key,
            value=value,
            **kwargs,
        )
