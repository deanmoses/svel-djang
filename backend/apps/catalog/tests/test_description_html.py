"""Tests for description_html in API responses."""

import pytest

from apps.catalog.models import Manufacturer, System
from apps.core.models import RecordReference


@pytest.fixture
def client():
    from django.test import Client

    return Client()


@pytest.fixture
def manufacturer_with_description(db):
    return Manufacturer.objects.create(
        name="Williams",
        slug="williams",
        description="A **legendary** pinball manufacturer.",
    )


@pytest.fixture
def system_with_description(db):
    return System.objects.create(
        name="WPC-95",
        slug="wpc-95",
        description="The final WPC generation.",
    )


class TestManufacturerDescriptionHtml:
    def test_detail_includes_description_html(
        self, client, manufacturer_with_description
    ):
        resp = client.get("/api/manufacturers/williams")
        assert resp.status_code == 200
        data = resp.json()
        assert "description_html" in data
        assert "<strong>legendary</strong>" in data["description_html"]

    def test_empty_description_returns_empty_html(self, client, db):
        Manufacturer.objects.create(name="Stern", slug="stern")
        resp = client.get("/api/manufacturers/stern")
        data = resp.json()
        assert data["description_html"] == ""

    @pytest.mark.django_db
    def test_entity_link_in_description(self, client, db):
        williams = Manufacturer.objects.create(name="Williams", slug="williams")
        System.objects.create(
            name="WPC-95",
            slug="wpc-95",
            manufacturer=williams,
            description=f"Made by [[manufacturer:id:{williams.pk}]].",
        )
        resp = client.get("/api/systems/wpc-95")
        data = resp.json()
        assert "/manufacturers/williams" in data["description_html"]
        assert "Williams" in data["description_html"]


class TestSystemDescriptionHtml:
    def test_detail_includes_description_html(self, client, system_with_description):
        resp = client.get("/api/systems/wpc-95")
        assert resp.status_code == 200
        data = resp.json()
        assert "description_html" in data
        assert data["description_html"] != ""

    def test_raw_description_also_present(self, client, system_with_description):
        resp = client.get("/api/systems/wpc-95")
        data = resp.json()
        assert data["description"] == "The final WPC generation."


@pytest.mark.django_db
class TestAdminMarkdownConversion:
    def test_authoring_to_storage_on_claim(self):
        """ProvenanceSaveMixin._to_claim_value converts [[type:slug]] to [[type:id:N]]."""
        from apps.catalog.admin import ManufacturerAdmin

        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        admin_instance = ManufacturerAdmin(Manufacturer, None)
        value = admin_instance._to_claim_value(
            "description", "Made by [[manufacturer:williams]]."
        )
        assert f"[[manufacturer:id:{mfr.pk}]]" in value
        assert "[[manufacturer:williams]]" not in value

    def test_non_markdown_field_unchanged(self):
        """Non-markdown fields pass through without conversion."""
        from apps.catalog.admin import ManufacturerAdmin

        admin_instance = ManufacturerAdmin(Manufacturer, None)
        value = admin_instance._to_claim_value("name", "Williams")
        assert value == "Williams"


@pytest.mark.django_db
class TestReferenceSync:
    def test_resolve_creates_references(self):
        """Resolving a manufacturer with links creates RecordReference rows."""
        from django.contrib.contenttypes.models import ContentType

        from apps.catalog.resolve import resolve_manufacturer
        from apps.provenance.models import Claim, Source

        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        system = System.objects.create(name="WPC-95", slug="wpc-95", manufacturer=mfr)
        source = Source.objects.create(name="test", priority=100)
        Claim.objects.assert_claim(
            mfr,
            "description",
            f"Uses [[system:id:{system.pk}]].",
            source=source,
        )
        resolve_manufacturer(mfr)

        mfr_ct = ContentType.objects.get_for_model(Manufacturer)
        refs = RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk)
        assert refs.count() == 1
        system_ct = ContentType.objects.get_for_model(System)
        assert refs.first().target_type == system_ct
        assert refs.first().target_id == system.pk

    def test_blanked_field_cleans_up_references(self):
        """When a description is blanked, stale RecordReference rows are removed."""
        from django.contrib.contenttypes.models import ContentType

        from apps.catalog.resolve import resolve_manufacturer
        from apps.provenance.models import Claim, Source

        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        system = System.objects.create(name="WPC-95", slug="wpc-95", manufacturer=mfr)
        source = Source.objects.create(name="test", priority=100)

        # Create a reference via description with a link
        Claim.objects.assert_claim(
            mfr,
            "description",
            f"Uses [[system:id:{system.pk}]].",
            source=source,
        )
        resolve_manufacturer(mfr)
        mfr_ct = ContentType.objects.get_for_model(Manufacturer)
        assert (
            RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk).count()
            == 1
        )

        # Deactivate the claim so description resolves to blank
        Claim.objects.filter(
            content_type=mfr_ct, object_id=mfr.pk, field_name="description"
        ).update(is_active=False)
        resolve_manufacturer(mfr)

        assert mfr.description == ""
        assert (
            RecordReference.objects.filter(source_type=mfr_ct, source_id=mfr.pk).count()
            == 0
        )


@pytest.mark.django_db
class TestApiPatchConversion:
    def test_patch_converts_authoring_to_storage(self):
        """API PATCH endpoint converts [[type:slug]] to [[type:id:N]]."""
        from django.contrib.auth import get_user_model
        from django.test import Client

        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        system = System.objects.create(name="WPC-95", slug="wpc-95", manufacturer=mfr)

        client = Client()
        client.force_login(user)
        resp = client.patch(
            f"/api/manufacturers/{mfr.slug}/claims/",
            {"fields": {"description": "Uses [[system:wpc-95]]."}},
            content_type="application/json",
        )
        assert resp.status_code == 200

        from apps.provenance.models import Claim

        claim = Claim.objects.filter(
            object_id=mfr.pk, field_name="description", is_active=True
        ).first()
        assert claim is not None
        assert f"[[system:id:{system.pk}]]" in claim.value
