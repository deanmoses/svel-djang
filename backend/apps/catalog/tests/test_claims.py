"""Tests for catalog/claims.py and provenance make_claim_key()."""

import pytest

from apps.catalog.claims import (
    build_relationship_claim,
    get_relationship_namespaces,
    make_authoritative_scope,
)
from apps.catalog.models import MachineModel, Manufacturer
from apps.catalog.tests.conftest import make_machine_model
from apps.provenance.models import make_claim_key

# ---------------------------------------------------------------------------
# make_claim_key (provenance utility)
# ---------------------------------------------------------------------------


class TestMakeClaimKey:
    def test_scalar_returns_field_name(self):
        assert make_claim_key("name") == "name"

    def test_with_identity_parts(self):
        key = make_claim_key("credit", person=42, role=7)
        assert key == "credit|person:42|role:7"

    def test_identity_parts_sorted(self):
        key = make_claim_key("credit", role=7, person=42)
        assert key == "credit|person:42|role:7"

    def test_none_becomes_null(self):
        key = make_claim_key("recipient", person=42, year=None)
        assert key == "recipient|person:42|year:null"

    def test_pipe_in_value_escaped(self):
        key = make_claim_key("credit", person="bad|value")
        assert key == "credit|person:bad%7Cvalue"

    def test_colon_in_value_escaped(self):
        key = make_claim_key("credit", person="bad:value")
        assert key == "credit|person:bad%3Avalue"

    def test_percent_in_value_escaped(self):
        key = make_claim_key("credit", person="100%")
        assert key == "credit|person:100%25"


# ---------------------------------------------------------------------------
# build_relationship_claim (catalog helper)
# ---------------------------------------------------------------------------


class TestBuildRelationshipClaim:
    def test_credit_claim(self, credit_targets):
        person_pk = credit_targets["persons"]["pat-lawlor"].pk
        role_pk = credit_targets["roles"]["design"].pk
        key, val = build_relationship_claim(
            "credit", {"person": person_pk, "role": role_pk}
        )
        assert key == f"credit|person:{person_pk}|role:{role_pk}"
        assert val == {"person": person_pk, "role": role_pk, "exists": True}

    def test_exists_false(self, credit_targets):
        person_pk = credit_targets["persons"]["pat-lawlor"].pk
        role_pk = credit_targets["roles"]["design"].pk
        _, val = build_relationship_claim(
            "credit", {"person": person_pk, "role": role_pk}, exists=False
        )
        assert val["exists"] is False

    def test_unknown_namespace_raises(self):
        with pytest.raises(ValueError, match="Unknown relationship namespace"):
            build_relationship_claim("bogus", {"person": 1, "role": 2})

    def test_missing_required_key_raises(self):
        with pytest.raises(ValueError, match="Missing required key"):
            build_relationship_claim("credit", {"person": 1})


# ---------------------------------------------------------------------------
# make_authoritative_scope
# ---------------------------------------------------------------------------


class TestMakeAuthoritativeScope:
    def test_builds_scope(self, db):
        m1 = make_machine_model(name="Game 1", slug="game-1")
        m2 = make_machine_model(name="Game 2", slug="game-2")
        scope = make_authoritative_scope(MachineModel, {m1.pk, m2.pk})
        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(MachineModel).pk
        assert scope == {(ct_id, m1.pk), (ct_id, m2.pk)}

    def test_empty_ids(self, db):
        scope = make_authoritative_scope(Manufacturer, set())
        assert scope == set()


# ---------------------------------------------------------------------------
# get_relationship_namespaces()
# ---------------------------------------------------------------------------


class TestRelationshipNamespaces:
    def test_contains_credit_and_theme(self):
        ns = get_relationship_namespaces()
        assert "credit" in ns
        assert "theme" in ns
