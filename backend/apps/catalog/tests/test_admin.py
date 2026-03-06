"""Tests for ProvenanceSaveMixin in catalog admin.

Verifies that saves on Manufacturer, Person, and MachineModel route
claim-controlled field changes through the provenance system.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.catalog.admin import MachineModelAdmin, ManufacturerAdmin, PersonAdmin
from apps.catalog.models import MachineModel, Manufacturer, Person, Title
from apps.provenance.models import Claim

User = get_user_model()


class _MockForm:
    """Minimal form stub — only the fields save_model reads."""

    def __init__(self, changed_data, cleaned_data):
        self.changed_data = changed_data
        self.cleaned_data = cleaned_data


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        "admin",
        "admin@example.com",
        "testpass",  # pragma: allowlist secret
    )


@pytest.fixture
def admin_request(superuser):
    request = RequestFactory().post("/")
    request.user = superuser
    return request


# ---------------------------------------------------------------------------
# ManufacturerAdmin
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestManufacturerAdminClaims:
    def test_changed_name_asserts_claim(self, admin_request):
        mfr = Manufacturer.objects.create(name="Gottlieb")
        mfr.name = "Gottlieb Updated"

        ma = ManufacturerAdmin(Manufacturer, AdminSite())
        form = _MockForm(["name"], {"name": "Gottlieb Updated", "trade_name": ""})
        ma.save_model(admin_request, mfr, form, change=True)

        claim = Claim.objects.get(
            content_type__model="manufacturer",
            object_id=mfr.pk,
            field_name="name",
            user=admin_request.user,
            is_active=True,
        )
        assert claim.value == "Gottlieb Updated"

    def test_changed_trade_name_asserts_claim(self, admin_request):
        mfr = Manufacturer.objects.create(name="Midway Manufacturing")
        mfr.trade_name = "Bally"

        ma = ManufacturerAdmin(Manufacturer, AdminSite())
        form = _MockForm(
            ["trade_name"], {"name": "Midway Manufacturing", "trade_name": "Bally"}
        )
        ma.save_model(admin_request, mfr, form, change=True)

        claim = Claim.objects.get(
            content_type__model="manufacturer",
            object_id=mfr.pk,
            field_name="trade_name",
            is_active=True,
        )
        assert claim.value == "Bally"

    def test_unchanged_field_creates_no_claim(self, admin_request):
        mfr = Manufacturer.objects.create(name="Williams")

        ma = ManufacturerAdmin(Manufacturer, AdminSite())
        form = _MockForm([], {"name": "Williams", "trade_name": ""})
        ma.save_model(admin_request, mfr, form, change=True)

        assert not Claim.objects.filter(
            object_id=mfr.pk, user=admin_request.user
        ).exists()

    def test_slug_change_does_not_assert_claim(self, admin_request):
        mfr = Manufacturer.objects.create(name="Bally")

        ma = ManufacturerAdmin(Manufacturer, AdminSite())
        form = _MockForm(
            ["slug"], {"name": "Bally", "trade_name": "", "slug": "bally-v2"}
        )
        ma.save_model(admin_request, mfr, form, change=True)

        assert not Claim.objects.filter(user=admin_request.user).exists()

    def test_resolve_runs_and_updates_model(self, admin_request):
        mfr = Manufacturer.objects.create(name="Gottlieb")
        mfr.name = "Gottlieb Renamed"

        ma = ManufacturerAdmin(Manufacturer, AdminSite())
        form = _MockForm(["name"], {"name": "Gottlieb Renamed", "trade_name": ""})
        ma.save_model(admin_request, mfr, form, change=True)

        mfr.refresh_from_db()
        assert mfr.name == "Gottlieb Renamed"


# ---------------------------------------------------------------------------
# PersonAdmin
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPersonAdminClaims:
    def test_changed_name_asserts_claim(self, admin_request):
        person = Person.objects.create(name="Steve Ritchie")
        person.name = "Steve Ritchie Jr."

        pa = PersonAdmin(Person, AdminSite())
        form = _MockForm(["name"], {"name": "Steve Ritchie Jr.", "bio": ""})
        pa.save_model(admin_request, person, form, change=True)

        claim = Claim.objects.get(
            content_type__model="person",
            object_id=person.pk,
            field_name="name",
            is_active=True,
        )
        assert claim.value == "Steve Ritchie Jr."

    def test_changed_bio_asserts_claim(self, admin_request):
        person = Person.objects.create(name="Pat Lawlor")
        person.bio = "Prolific designer."

        pa = PersonAdmin(Person, AdminSite())
        form = _MockForm(["bio"], {"name": "Pat Lawlor", "bio": "Prolific designer."})
        pa.save_model(admin_request, person, form, change=True)

        claim = Claim.objects.get(
            content_type__model="person",
            object_id=person.pk,
            field_name="bio",
            is_active=True,
        )
        assert claim.value == "Prolific designer."


# ---------------------------------------------------------------------------
# MachineModelAdmin
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMachineModelAdminClaims:
    def test_changed_year_asserts_claim(self, admin_request):
        pm = MachineModel.objects.create(name="Medieval Madness")
        pm.year = 1997

        mma = MachineModelAdmin(MachineModel, AdminSite())
        form = _MockForm(["year"], {"name": "Medieval Madness", "year": 1997})
        mma.save_model(admin_request, pm, form, change=True)

        claim = Claim.objects.get(
            content_type__model="machinemodel",
            object_id=pm.pk,
            field_name="year",
            is_active=True,
        )
        assert claim.value == 1997

    def test_manufacturer_fk_serialized_as_slug(self, admin_request):
        mfr = Manufacturer.objects.create(name="Williams", slug="williams")
        pm = MachineModel.objects.create(name="Medieval Madness")
        pm.manufacturer = mfr

        mma = MachineModelAdmin(MachineModel, AdminSite())
        form = _MockForm(
            ["manufacturer"], {"name": "Medieval Madness", "manufacturer": mfr}
        )
        mma.save_model(admin_request, pm, form, change=True)

        claim = Claim.objects.get(
            content_type__model="machinemodel",
            object_id=pm.pk,
            field_name="manufacturer",
            is_active=True,
        )
        assert claim.value == "williams"

    def test_manufacturer_cleared_deactivates_user_claim(self, admin_request):
        # Pre-existing user claim for manufacturer.
        mfr = Manufacturer.objects.create(name="Bally")
        pm = MachineModel.objects.create(name="Eight Ball", manufacturer=mfr)
        prior_claim = Claim.objects.assert_claim(
            pm, "manufacturer", "Bally", user=admin_request.user
        )

        # Admin clears the manufacturer field.
        pm.manufacturer = None
        mma = MachineModelAdmin(MachineModel, AdminSite())
        form = _MockForm(["manufacturer"], {"name": "Eight Ball", "manufacturer": None})
        mma.save_model(admin_request, pm, form, change=True)

        prior_claim.refresh_from_db()
        assert not prior_claim.is_active
        assert not Claim.objects.filter(
            object_id=pm.pk, field_name="manufacturer", is_active=True
        ).exists()

    def test_title_fk_serialized_as_opdb_id(self, admin_request):
        title = Title.objects.create(opdb_id="G5pe4", name="Medieval Madness")
        pm = MachineModel.objects.create(name="Medieval Madness")
        pm.title = title

        mma = MachineModelAdmin(MachineModel, AdminSite())
        form = _MockForm(["title"], {"name": "Medieval Madness", "title": title})
        mma.save_model(admin_request, pm, form, change=True)

        claim = Claim.objects.get(
            content_type__model="machinemodel",
            object_id=pm.pk,
            field_name="title",
            is_active=True,
        )
        assert claim.value == "G5pe4"

    def test_non_claim_field_alias_of_creates_no_claim(self, admin_request):
        parent = MachineModel.objects.create(name="Medieval Madness")
        pm = MachineModel.objects.create(name="Medieval Madness LE")
        pm.alias_of = parent

        mma = MachineModelAdmin(MachineModel, AdminSite())
        form = _MockForm(
            ["alias_of"], {"name": "Medieval Madness LE", "alias_of": parent}
        )
        mma.save_model(admin_request, pm, form, change=True)

        assert not Claim.objects.filter(
            object_id=pm.pk, user=admin_request.user
        ).exists()

    def test_new_object_asserts_claims_for_filled_fields(self, admin_request):
        pm = MachineModel.objects.create(name="Firepower")

        mma = MachineModelAdmin(MachineModel, AdminSite())
        form = _MockForm(
            ["name", "year"],
            {"name": "Firepower", "year": 1980},
        )
        mma.save_model(admin_request, pm, form, change=False)

        assert Claim.objects.filter(
            content_type__model="machinemodel", object_id=pm.pk, field_name="name"
        ).exists()
        assert Claim.objects.filter(
            content_type__model="machinemodel", object_id=pm.pk, field_name="year"
        ).exists()
