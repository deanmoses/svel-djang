"""Admin contract tests.

Verifies that catalog models are not registered with Django admin and that
provenance models used for inspection cannot be written through admin.
"""

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.catalog.models import (
    Cabinet,
    CorporateEntity,
    CreditRole,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    Location,
    MachineModel,
    Manufacturer,
    Person,
    RewardType,
    Series,
    System,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
    Theme,
    Title,
)
from apps.provenance.admin import ClaimAdmin
from apps.provenance.models import Claim


class TestCatalogModelsNotInAdmin:
    def test_catalog_models_not_registered(self):
        """No catalog model may be registered with Django admin."""
        catalog_models = [
            Cabinet,
            CorporateEntity,
            CreditRole,
            DisplaySubtype,
            DisplayType,
            Franchise,
            GameFormat,
            GameplayFeature,
            Location,
            MachineModel,
            Manufacturer,
            Person,
            RewardType,
            Series,
            System,
            Tag,
            TechnologyGeneration,
            TechnologySubgeneration,
            Theme,
            Title,
        ]
        registered = list(admin.site._registry)
        for model in catalog_models:
            assert model not in registered, (
                f"{model.__name__} is registered in Django admin — "
                "catalog models must not be (see docs/plans/ValidationFix3.md)"
            )


class TestClaimAdminIsReadOnly:
    def test_no_add_permission(self):
        request = RequestFactory().get("/")
        ca = ClaimAdmin(Claim, AdminSite())
        assert not ca.has_add_permission(request)

    def test_no_change_permission(self):
        request = RequestFactory().get("/")
        ca = ClaimAdmin(Claim, AdminSite())
        assert not ca.has_change_permission(request)

    def test_no_delete_permission(self):
        request = RequestFactory().get("/")
        ca = ClaimAdmin(Claim, AdminSite())
        assert not ca.has_delete_permission(request)
