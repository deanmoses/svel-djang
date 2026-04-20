"""Tests for shared validators."""

from __future__ import annotations

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.core.validators import bulk_create_validated, validate_no_mojibake
from apps.catalog.tests.conftest import make_machine_model


class TestValidateNoMojibake:
    """validate_no_mojibake rejects encoding-corrupted text."""

    @pytest.mark.parametrize(
        "value",
        [
            "Medieval Madness",
            "D. Gottlieb & Company",
            "Bally/Williams",
            "René Lalonde",
            "Günter",
            "São Paulo",
            "naïve",
            "Señor",
            "François",
            "Łukasz",
            "Rock’n’Roll",
            "Pinball™",
            "Bally — Midway",
            "東京",
            "🎱 Pinball",
            "",
            None,
        ],
    )
    def test_allows_valid_text(self, value):
        validate_no_mojibake(value)

    @pytest.mark.parametrize(
        ("value", "match"),
        [
            ("MediÃ©val", "mojibake"),
            ("Ã¼ber", "mojibake"),
            ("Ã±o", "mojibake"),
            ("FranÃ§ois", "mojibake"),
            ("PokÃ©mon", "mojibake"),
            ("\u00e2\u20ac\u2122s", "mojibake"),  # â€™s
            ("\u00e2\u20ac\u201d", "mojibake"),  # â€” (em dash)
            ("â„¢", "mojibake"),
            ("â€”", "mojibake"),
            ("ðŸŽ± Pinball", "mojibake"),
            ("hello\ufffd", "replacement character"),
            ("\ufffd", "replacement character"),
        ],
    )
    def test_rejects_mojibake_and_replacement_characters(self, value, match):
        with pytest.raises(ValidationError, match=match):
            validate_no_mojibake(value)


@pytest.mark.django_db
class TestMojibakeClaimsApiIntegration:
    """Mojibake is rejected when submitted via the claims PATCH endpoint."""

    @pytest.fixture
    def user(self):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username="editor")

    @pytest.fixture
    def pm(self):

        return make_machine_model(
            name="Medieval Madness",
            slug="medieval-madness",
            year=1997,
        )

    def test_rejects_mojibake_name_via_claims_api(self, client, user, pm):
        client.force_login(user)
        resp = client.patch(
            f"/api/models/{pm.slug}/claims/",
            data={"fields": {"name": "MediÃ©val Madness"}, "note": ""},
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_accepts_valid_accented_name_via_claims_api(self, client, user, pm):
        client.force_login(user)
        resp = client.patch(
            f"/api/models/{pm.slug}/claims/",
            data={"fields": {"name": "Médiéval Madness"}, "note": ""},
            content_type="application/json",
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMojibakeBulkAssertClaims:
    """Mojibake is rejected when written via bulk_assert_claims (ingestion path)."""

    @pytest.fixture
    def source(self):
        from apps.provenance.models import Source

        return Source.objects.create(
            name="Test", slug="test", source_type="database", priority=10
        )

    @pytest.fixture
    def pm(self):

        return make_machine_model(
            name="Medieval Madness",
            slug="medieval-madness",
            year=1997,
        )

    def test_rejects_mojibake_name_claim(self, source, pm):
        from apps.provenance.models import Claim

        ct_id = ContentType.objects.get_for_model(pm).pk
        pending = [
            Claim(
                content_type_id=ct_id,
                object_id=pm.pk,
                field_name="name",
                value="MediÃ©val Madness",
            ),
        ]
        # Batch validation logs and skips mojibake claims instead of raising.
        result = Claim.objects.bulk_assert_claims(source, pending)
        assert result["validation_rejected"] == 1
        assert result["created"] == 0

    def test_allows_valid_accented_name_claim(self, source, pm):
        from apps.provenance.models import Claim

        ct_id = ContentType.objects.get_for_model(pm).pk
        pending = [
            Claim(
                content_type_id=ct_id,
                object_id=pm.pk,
                field_name="name",
                value="Médiéval Madness",
            ),
        ]
        result = Claim.objects.bulk_assert_claims(source, pending)
        assert result["created"] == 1

    def test_allows_mojibake_in_alias_claim(self, source, pm):
        """Alias fields do NOT have the mojibake validator — garbled source
        names are legitimate lookup values."""
        from apps.catalog.models import Manufacturer

        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        ct_id = ContentType.objects.get_for_model(mfr).pk

        from apps.provenance.models import Claim

        pending = [
            Claim(
                content_type_id=ct_id,
                object_id=mfr.pk,
                field_name="manufacturer_alias",
                claim_key="manufacturer_alias|alias_value:garbled",
                value={
                    "alias_value": "GÃ¶ttlieb",
                    "alias_display": "GÃ¶ttlieb",
                    "exists": True,
                },
            ),
        ]
        # Should NOT raise — alias values are exempt from mojibake validation
        result = Claim.objects.bulk_assert_claims(source, pending)
        assert result["created"] == 1


@pytest.mark.django_db
class TestMojibakeBulkCreateValidated:
    """Mojibake is rejected when using bulk_create_validated (ingestion path)."""

    def test_rejects_mojibake_name_in_bulk_create(self):
        from apps.catalog.models import MachineModel

        objs = [MachineModel(name="MediÃ©val Madness", slug="medieval-madness")]
        with pytest.raises(ValidationError, match="mojibake"):
            bulk_create_validated(MachineModel, objs)

    def test_accepts_valid_name_in_bulk_create(self):
        from apps.catalog.models import MachineModel, Title

        title = Title.objects.create(
            name="Médiéval Madness", slug="medieval-madness-title"
        )
        objs = [
            MachineModel(name="Médiéval Madness", slug="medieval-madness", title=title)
        ]
        created = bulk_create_validated(MachineModel, objs)
        assert len(created) == 1
