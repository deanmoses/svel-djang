"""Tests for ClaimManager.bulk_assert_claims()."""

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.catalog.models import MachineModel, Manufacturer
from apps.provenance.models import Claim, Source


@pytest.fixture
def source(db):
    return Source.objects.create(
        name="IPDB", slug="ipdb", source_type="database", priority=10
    )


@pytest.fixture
def other_source(db):
    return Source.objects.create(
        name="OPDB", slug="opdb", source_type="database", priority=20
    )


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name="Williams")


@pytest.fixture
def pm1(db):
    return MachineModel.objects.create(name="Medieval Madness", year=1997)


@pytest.fixture
def pm2(db):
    return MachineModel.objects.create(name="Monster Bash", year=1998)


@pytest.fixture
def ct_id(db):
    return ContentType.objects.get_for_model(MachineModel).pk


class TestBulkAssertClaimsCreate:
    """First run: no existing claims, everything is new."""

    def test_creates_all_claims(self, source, ct_id, pm1, pm2):
        pending = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1997
            ),
            Claim(
                content_type_id=ct_id,
                object_id=pm1.pk,
                field_name="name",
                value="Medieval Madness",
            ),
            Claim(
                content_type_id=ct_id, object_id=pm2.pk, field_name="year", value=1998
            ),
        ]
        stats = Claim.objects.bulk_assert_claims(source, pending)

        assert stats["created"] == 3
        assert stats["unchanged"] == 0
        assert stats["superseded"] == 0
        assert stats["duplicates_removed"] == 0

        assert Claim.objects.filter(is_active=True, source=source).count() == 3

    def test_all_created_claims_are_active(self, source, ct_id, pm1):
        pending = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1997
            ),
        ]
        Claim.objects.bulk_assert_claims(source, pending)

        claim = pm1.claims.get(source=source, field_name="year", is_active=True)
        assert claim.value == 1997


class TestBulkAssertClaimsIdempotent:
    """Second run with same data: nothing should be written."""

    def test_unchanged_on_second_run(self, source, ct_id, pm1, pm2):
        pending = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1997
            ),
            Claim(
                content_type_id=ct_id, object_id=pm2.pk, field_name="year", value=1998
            ),
        ]
        Claim.objects.bulk_assert_claims(source, pending)

        pending2 = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1997
            ),
            Claim(
                content_type_id=ct_id, object_id=pm2.pk, field_name="year", value=1998
            ),
        ]
        stats = Claim.objects.bulk_assert_claims(source, pending2)

        assert stats["created"] == 0
        assert stats["superseded"] == 0
        assert stats["unchanged"] == 2

        assert Claim.objects.filter(is_active=True, source=source).count() == 2
        assert Claim.objects.filter(is_active=False, source=source).count() == 0


class TestBulkAssertClaimsSupersede:
    """Changed values should deactivate old claims and create new ones."""

    def test_supersedes_changed_value(self, source, ct_id, pm1):
        pending1 = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1997
            )
        ]
        Claim.objects.bulk_assert_claims(source, pending1)

        pending2 = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1998
            )
        ]
        stats = Claim.objects.bulk_assert_claims(source, pending2)

        assert stats["created"] == 1
        assert stats["superseded"] == 1
        assert stats["unchanged"] == 0

        assert (
            pm1.claims.filter(source=source, field_name="year", is_active=True).count()
            == 1
        )
        assert (
            pm1.claims.filter(source=source, field_name="year", is_active=False).count()
            == 1
        )

        active = pm1.claims.get(source=source, field_name="year", is_active=True)
        assert active.value == 1998

    def test_supersedes_changed_citation(self, source, ct_id, pm1):
        pending1 = [
            Claim(
                content_type_id=ct_id,
                object_id=pm1.pk,
                field_name="year",
                value=1997,
                citation="old",
            )
        ]
        Claim.objects.bulk_assert_claims(source, pending1)

        pending2 = [
            Claim(
                content_type_id=ct_id,
                object_id=pm1.pk,
                field_name="year",
                value=1997,
                citation="new",
            )
        ]
        stats = Claim.objects.bulk_assert_claims(source, pending2)

        assert stats["created"] == 1
        assert stats["superseded"] == 1


class TestBulkAssertClaimsDeduplicate:
    """Duplicate (object_id, field_name) pairs: last-write-wins."""

    def test_deduplicates_pending(self, source, ct_id, pm1):
        pending = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1997
            ),
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1998
            ),
        ]
        stats = Claim.objects.bulk_assert_claims(source, pending)

        assert stats["duplicates_removed"] == 1
        assert stats["created"] == 1

        active = pm1.claims.get(source=source, field_name="year", is_active=True)
        assert active.value == 1998

    def test_no_constraint_violation_on_duplicates(self, source, ct_id, pm1):
        pending = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="name", value="V1"
            ),
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="name", value="V2"
            ),
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="name", value="V3"
            ),
        ]
        stats = Claim.objects.bulk_assert_claims(source, pending)
        assert stats["duplicates_removed"] == 2
        assert (
            pm1.claims.filter(source=source, field_name="name", is_active=True).count()
            == 1
        )


class TestBulkAssertClaimsIsolation:
    """Claims from different sources should not interfere."""

    def test_does_not_touch_other_sources(self, source, other_source, ct_id, pm1):
        Claim.objects.assert_claim(pm1, "year", 1997, source=other_source)

        pending = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1998
            )
        ]
        Claim.objects.bulk_assert_claims(source, pending)

        other_claim = pm1.claims.get(
            source=other_source, field_name="year", is_active=True
        )
        assert other_claim.value == 1997

        this_claim = pm1.claims.get(source=source, field_name="year", is_active=True)
        assert this_claim.value == 1998


class TestBulkAssertClaimsSourceSet:
    """The source FK should be set by bulk_assert_claims."""

    def test_source_is_set_on_pending_claims(self, source, ct_id, pm1):
        pending = [
            Claim(
                content_type_id=ct_id, object_id=pm1.pk, field_name="year", value=1997
            )
        ]
        Claim.objects.bulk_assert_claims(source, pending)

        claim = pm1.claims.get(field_name="year", is_active=True)
        assert claim.source == source


class TestBulkAssertClaimsSweep:
    """sweep_field + authoritative_scope deactivate stale claims."""

    def test_sweep_deactivates_stale_claim(self, source, ct_id, pm1):
        """A claim no longer in the pending set is swept (deactivated)."""
        from apps.catalog.claims import build_relationship_claim

        key1, val1 = build_relationship_claim(
            "credit", {"person_slug": "pat-lawlor", "role": "design"}
        )
        key2, val2 = build_relationship_claim(
            "credit", {"person_slug": "john-youssi", "role": "art"}
        )
        pending1 = [
            Claim(
                content_type_id=ct_id,
                object_id=pm1.pk,
                field_name="credit",
                claim_key=key1,
                value=val1,
            ),
            Claim(
                content_type_id=ct_id,
                object_id=pm1.pk,
                field_name="credit",
                claim_key=key2,
                value=val2,
            ),
        ]
        auth_scope = {(ct_id, pm1.pk)}
        Claim.objects.bulk_assert_claims(
            source,
            pending1,
            sweep_field="credit",
            authoritative_scope=auth_scope,
        )

        assert Claim.objects.filter(source=source, is_active=True).count() == 2

        # Second run: only one credit remains.
        pending2 = [
            Claim(
                content_type_id=ct_id,
                object_id=pm1.pk,
                field_name="credit",
                claim_key=key1,
                value=val1,
            ),
        ]
        stats = Claim.objects.bulk_assert_claims(
            source,
            pending2,
            sweep_field="credit",
            authoritative_scope=auth_scope,
        )

        assert stats["swept"] == 1
        assert Claim.objects.filter(source=source, is_active=True).count() == 1
        remaining = Claim.objects.get(source=source, is_active=True)
        assert remaining.claim_key == key1

    def test_sweep_with_zero_pending_deactivates_all(self, source, ct_id, pm1):
        """authoritative_scope ensures stale claims are swept even when pending is empty."""
        from apps.catalog.claims import build_relationship_claim

        key, val = build_relationship_claim(
            "credit", {"person_slug": "pat-lawlor", "role": "design"}
        )
        Claim.objects.bulk_assert_claims(
            source,
            [
                Claim(
                    content_type_id=ct_id,
                    object_id=pm1.pk,
                    field_name="credit",
                    claim_key=key,
                    value=val,
                )
            ],
            sweep_field="credit",
            authoritative_scope={(ct_id, pm1.pk)},
        )

        assert Claim.objects.filter(source=source, is_active=True).count() == 1

        # Second run with empty pending but same authoritative scope.
        stats = Claim.objects.bulk_assert_claims(
            source,
            [],
            sweep_field="credit",
            authoritative_scope={(ct_id, pm1.pk)},
        )

        assert stats["swept"] == 1
        assert Claim.objects.filter(source=source, is_active=True).count() == 0

    def test_sweep_does_not_touch_other_field_names(self, source, ct_id, pm1):
        """Sweep only affects claims matching the sweep_field."""
        from apps.catalog.claims import build_relationship_claim

        # A scalar claim.
        Claim.objects.assert_claim(pm1, "name", "Medieval Madness", source=source)

        # A credit claim.
        key, val = build_relationship_claim(
            "credit", {"person_slug": "pat-lawlor", "role": "design"}
        )
        Claim.objects.bulk_assert_claims(
            source,
            [
                Claim(
                    content_type_id=ct_id,
                    object_id=pm1.pk,
                    field_name="credit",
                    claim_key=key,
                    value=val,
                )
            ],
            sweep_field="credit",
            authoritative_scope={(ct_id, pm1.pk)},
        )

        # Sweep credits with empty pending — scalar should survive.
        Claim.objects.bulk_assert_claims(
            source,
            [],
            sweep_field="credit",
            authoritative_scope={(ct_id, pm1.pk)},
        )

        assert (
            Claim.objects.filter(
                source=source, field_name="name", is_active=True
            ).count()
            == 1
        )
        assert (
            Claim.objects.filter(
                source=source, field_name="credit", is_active=True
            ).count()
            == 0
        )

    def test_sweep_scoped_to_authoritative_models(self, source, ct_id, pm1, pm2):
        """Sweep only affects entities in the authoritative scope."""
        from apps.catalog.claims import build_relationship_claim

        key, val = build_relationship_claim(
            "credit", {"person_slug": "pat-lawlor", "role": "design"}
        )
        # Create credit claims on both machines.
        for pm in (pm1, pm2):
            Claim.objects.bulk_assert_claims(
                source,
                [
                    Claim(
                        content_type_id=ct_id,
                        object_id=pm.pk,
                        field_name="credit",
                        claim_key=key,
                        value=val,
                    )
                ],
                sweep_field="credit",
                authoritative_scope={(ct_id, pm.pk)},
            )

        assert Claim.objects.filter(source=source, is_active=True).count() == 2

        # Sweep pm1 only with empty pending.
        Claim.objects.bulk_assert_claims(
            source,
            [],
            sweep_field="credit",
            authoritative_scope={(ct_id, pm1.pk)},
        )

        # pm1's claim swept, pm2's untouched.
        assert (
            Claim.objects.filter(
                source=source, object_id=pm1.pk, is_active=True
            ).count()
            == 0
        )
        assert (
            Claim.objects.filter(
                source=source, object_id=pm2.pk, is_active=True
            ).count()
            == 1
        )
