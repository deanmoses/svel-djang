"""Tests for CitationInstance model behavior and admin."""

import pytest
from django.contrib import admin
from django.db.models import ProtectedError
from django.test import RequestFactory

from apps.citation.models import CitationSource
from apps.provenance.admin import CitationInstanceAdmin
from apps.provenance.models import CitationInstance, Claim, Source


@pytest.fixture
def citation_source(db):
    return CitationSource.objects.create(
        name="The Encyclopedia of Pinball", source_type="book"
    )


@pytest.fixture
def provenance_source(db):
    return Source.objects.create(
        name="Test Source", slug="test-source", source_type="editorial"
    )


@pytest.fixture
def claim(db, provenance_source):
    from django.contrib.contenttypes.models import ContentType

    # Use CitationSource as a convenient target — any model works
    ct = ContentType.objects.get_for_model(CitationSource)
    cs = CitationSource.objects.create(name="Target", source_type="web")
    return Claim.objects.create(
        content_type=ct,
        object_id=cs.pk,
        source=provenance_source,
        field_name="name",
        claim_key="name",
        value="Target",
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestCitationInstanceCreation:
    def test_valid_with_claim(self, citation_source, claim):
        ci = CitationInstance.objects.create(
            citation_source=citation_source,
            claim=claim,
            locator="p. 30",
        )
        assert ci.pk is not None
        assert ci.claim == claim
        assert ci.locator == "p. 30"

    def test_valid_without_claim(self, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source,
            locator="front",
        )
        assert ci.pk is not None
        assert ci.claim is None

    def test_valid_with_empty_locator(self, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source,
        )
        assert ci.locator == ""

    def test_created_at_set(self, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source,
        )
        assert ci.created_at is not None


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestCitationInstanceImmutability:
    def test_save_raises_on_update(self, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source,
            locator="p. 30",
        )
        ci.locator = "p. 31"
        with pytest.raises(ValueError, match="immutable"):
            ci.save()


# ---------------------------------------------------------------------------
# PROTECT behavior
# ---------------------------------------------------------------------------


class TestCitationInstanceProtect:
    def test_protect_prevents_source_delete(self, citation_source):
        CitationInstance.objects.create(citation_source=citation_source)
        with pytest.raises(ProtectedError):
            citation_source.delete()

    def test_protect_prevents_claim_delete(self, citation_source, claim):
        CitationInstance.objects.create(citation_source=citation_source, claim=claim)
        with pytest.raises(ProtectedError):
            claim.delete()


# ---------------------------------------------------------------------------
# __str__
# ---------------------------------------------------------------------------


class TestCitationInstanceStr:
    def test_with_locator(self, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source,
            locator="p. 30",
        )
        assert str(ci) == f"Citation: {citation_source.pk} @ p. 30"

    def test_without_locator(self, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source,
        )
        assert str(ci) == f"Citation: {citation_source.pk}"


# ---------------------------------------------------------------------------
# Reverse relations
# ---------------------------------------------------------------------------


class TestCitationInstanceReverseRelations:
    def test_source_instances(self, citation_source):
        ci = CitationInstance.objects.create(
            citation_source=citation_source, locator="p. 30"
        )
        assert ci in citation_source.instances.all()

    def test_claim_citation_instances(self, citation_source, claim):
        ci = CitationInstance.objects.create(
            citation_source=citation_source, claim=claim
        )
        assert ci in claim.citation_instances.all()


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class TestCitationInstanceAdmin:
    @pytest.fixture
    def admin_instance(self):
        return CitationInstanceAdmin(CitationInstance, admin.site)

    def test_registered_in_admin(self):
        assert CitationInstance in admin.site._registry

    def test_is_read_only(self, admin_instance):
        factory = RequestFactory()
        request = factory.get("/")
        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_change_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False
