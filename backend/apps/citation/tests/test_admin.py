"""Tests for citation admin configuration."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from django.test import RequestFactory

from apps.citation.admin import CitationSourceAdmin
from apps.citation.models import CitationSource, CitationSourceLink

User = get_user_model()

LinkFormSetCreate = inlineformset_factory(
    CitationSource,
    CitationSourceLink,
    fields=("link_type", "url", "label"),
    extra=1,
    can_delete=True,
)
LinkFormSetUpdate = inlineformset_factory(
    CitationSource,
    CitationSourceLink,
    fields=("link_type", "url", "label"),
    extra=0,
    can_delete=True,
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@test.com",
        password="password",  # pragma: allowlist secret
    )


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def admin_instance():
    return CitationSourceAdmin(CitationSource, admin.site)


class TestAdminRegistration:
    def test_citation_source_registered(self):
        assert CitationSource in admin.site._registry

    def test_citation_source_link_not_standalone(self):
        assert CitationSourceLink not in admin.site._registry


class TestCitationSourceAdminPermissions:
    def test_delete_permission_denied(
        self, admin_instance, request_factory, admin_user
    ):
        request = request_factory.get("/")
        request.user = admin_user
        assert admin_instance.has_delete_permission(request) is False

    def test_delete_permission_denied_with_obj(
        self, admin_instance, request_factory, admin_user, citation_source
    ):
        request = request_factory.get("/")
        request.user = admin_user
        assert admin_instance.has_delete_permission(request, citation_source) is False


class TestCitationSourceAdminReadonlyFields:
    def test_parent_editable_on_create(
        self, admin_instance, request_factory, admin_user
    ):
        request = request_factory.get("/")
        request.user = admin_user
        readonly = admin_instance.get_readonly_fields(request, obj=None)
        assert "parent" not in readonly

    def test_parent_readonly_on_change(
        self, admin_instance, request_factory, admin_user, citation_source
    ):
        request = request_factory.get("/")
        request.user = admin_user
        readonly = admin_instance.get_readonly_fields(request, obj=citation_source)
        assert "parent" in readonly

    def test_created_by_always_readonly(
        self, admin_instance, request_factory, admin_user
    ):
        request = request_factory.get("/")
        request.user = admin_user
        # Readonly on create
        readonly_create = admin_instance.get_readonly_fields(request, obj=None)
        assert "created_by" in readonly_create
        assert "updated_by" in readonly_create


class TestCitationSourceAdminAttribution:
    def test_created_by_set_on_create(
        self, admin_instance, request_factory, admin_user
    ):
        request = request_factory.post("/")
        request.user = admin_user
        obj = CitationSource(name="Test", source_type="book")
        admin_instance.save_model(request, obj, form=None, change=False)
        assert obj.created_by == admin_user
        assert obj.updated_by == admin_user

    def test_updated_by_set_on_change(
        self, admin_instance, request_factory, admin_user, citation_source
    ):
        request = request_factory.post("/")
        request.user = admin_user
        admin_instance.save_model(request, citation_source, form=None, change=True)
        assert citation_source.updated_by == admin_user
        # created_by should not be overwritten on change
        assert citation_source.created_by is None


class TestCitationSourceLinkInlineAttribution:
    """Test that save_formset auto-populates created_by/updated_by on inline links."""

    def test_created_by_set_on_new_link(
        self, admin_instance, request_factory, admin_user, citation_source
    ):
        data = {
            "links-TOTAL_FORMS": "1",
            "links-INITIAL_FORMS": "0",
            "links-0-link_type": "homepage",
            "links-0-url": "https://example.com",
            "links-0-label": "Example",
        }
        formset = LinkFormSetCreate(data, instance=citation_source, prefix="links")
        assert formset.is_valid(), formset.errors

        request = request_factory.post("/")
        request.user = admin_user
        admin_instance.save_formset(request, form=None, formset=formset, change=True)

        link = CitationSourceLink.objects.get(citation_source=citation_source)
        assert link.created_by == admin_user
        assert link.updated_by == admin_user

    def test_updated_by_set_on_existing_link(
        self, admin_instance, request_factory, admin_user, citation_source
    ):
        link = CitationSourceLink.objects.create(
            citation_source=citation_source,
            link_type="homepage",
            url="https://example.com",
            label="Old Label",
        )
        assert link.created_by is None

        data = {
            "links-TOTAL_FORMS": "1",
            "links-INITIAL_FORMS": "1",
            "links-0-id": str(link.pk),
            "links-0-link_type": "homepage",
            "links-0-url": "https://example.com",
            "links-0-label": "New Label",
        }
        formset = LinkFormSetUpdate(data, instance=citation_source, prefix="links")
        assert formset.is_valid(), formset.errors

        request = request_factory.post("/")
        request.user = admin_user
        admin_instance.save_formset(request, form=None, formset=formset, change=True)

        link.refresh_from_db()
        assert link.updated_by == admin_user
        # created_by should NOT be set on update of existing record
        assert link.created_by is None
