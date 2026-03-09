"""Tests for the ingest_pinbase_models command."""

import json
import tempfile

import pytest
from django.core.management import call_command

from apps.catalog.models import MachineModel
from apps.catalog.resolve import resolve_model
from apps.provenance.models import Claim, Source


@pytest.fixture
def opdb_source(db):
    return Source.objects.create(
        slug="opdb", name="OPDB", source_type="database", priority=200
    )


@pytest.fixture
def model_with_opdb_name(db, opdb_source):
    """A MachineModel with an OPDB name claim containing an abbreviation."""
    mm = MachineModel.objects.create(
        name="Foo (LE)",
        opdb_id="Gtest-Mtest",
    )
    Claim.objects.bulk_assert_claims(
        opdb_source,
        [
            Claim(
                content_type=mm.claims.model.content_type_field.related_model.objects.get_for_model(
                    MachineModel
                ),
                object_id=mm.pk,
                field_name="name",
                value="Foo (LE)",
            )
        ],
    )
    return mm


@pytest.fixture
def model_with_opdb_name_simple(db, opdb_source):
    """A MachineModel with an OPDB name claim — simpler setup."""
    from django.contrib.contenttypes.models import ContentType

    mm = MachineModel.objects.create(
        name="Foo (LE)",
        opdb_id="Gtest-Mtest",
    )
    ct = ContentType.objects.get_for_model(MachineModel)
    Claim.objects.bulk_assert_claims(
        opdb_source,
        [
            Claim(
                content_type_id=ct.pk,
                object_id=mm.pk,
                field_name="name",
                value="Foo (LE)",
            )
        ],
    )
    return mm


def _write_models_json(entries):
    """Write entries to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(entries, f)
    f.close()
    return f.name


@pytest.mark.django_db
class TestIngestPinbaseModels:
    def test_creates_name_claim(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        path = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Foo (Limited Edition)"}]
        )

        call_command("ingest_pinbase_models", path=path)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="name", is_active=True)
        assert claim.value == "Foo (Limited Edition)"

    def test_pinbase_wins_resolution(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        path = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Foo (Limited Edition)"}]
        )

        call_command("ingest_pinbase_models", path=path)
        resolve_model(mm)
        mm.refresh_from_db()

        assert mm.name == "Foo (Limited Edition)"

    def test_skips_unknown_opdb_id(self, db):
        path = _write_models_json([{"opdb_id": "Gfake-Mfake", "name": "Nonexistent"}])
        # Should not raise
        call_command("ingest_pinbase_models", path=path)

    def test_idempotent(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        path = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Foo (Limited Edition)"}]
        )

        call_command("ingest_pinbase_models", path=path)
        call_command("ingest_pinbase_models", path=path)

        source = Source.objects.get(slug="pinbase")
        assert (
            mm.claims.filter(source=source, field_name="name", is_active=True).count()
            == 1
        )

    def test_description_claim(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        path = _write_models_json(
            [
                {
                    "opdb_id": "Gtest-Mtest",
                    "name": "Foo (Limited Edition)",
                    "description": "A test description",
                }
            ]
        )

        call_command("ingest_pinbase_models", path=path)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="description", is_active=True)
        assert claim.value == "A test description"

    def test_display_type_claim(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        path = _write_models_json(
            [
                {
                    "opdb_id": "Gtest-Mtest",
                    "name": "Foo (Limited Edition)",
                    "display_type_slug": "alphanumeric",
                }
            ]
        )

        call_command("ingest_pinbase_models", path=path)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="display_type", is_active=True)
        assert claim.value == "alphanumeric"

    def test_variant_of_sets_alias_of(self, db):
        """variant_of correctly sets alias_of FK."""
        parent = MachineModel.objects.create(
            name="Parent Model", opdb_id="Gtest-Mparent"
        )
        child = MachineModel.objects.create(name="Child Model", opdb_id="Gtest-Mchild")
        path = _write_models_json(
            [
                {"slug": "parent-model", "opdb_id": "Gtest-Mparent"},
                {
                    "slug": "child-model",
                    "opdb_id": "Gtest-Mchild",
                    "variant_of": "parent-model",
                },
            ]
        )

        call_command("ingest_pinbase_models", path=path)

        child.refresh_from_db()
        assert child.alias_of == parent

    def test_variant_of_overrides_ingest(self, db):
        """variant_of from pinbase overrides a wrong alias_of from ingest_opdb."""
        wrong_parent = MachineModel.objects.create(
            name="Wrong Parent", opdb_id="Gtest-Mwrong"
        )
        right_parent = MachineModel.objects.create(
            name="Right Parent", opdb_id="Gtest-Mright"
        )
        child = MachineModel.objects.create(
            name="Child", opdb_id="Gtest-Mchild", alias_of=wrong_parent
        )
        path = _write_models_json(
            [
                {"slug": "right-parent", "opdb_id": "Gtest-Mright"},
                {
                    "slug": "child-model",
                    "opdb_id": "Gtest-Mchild",
                    "variant_of": "right-parent",
                },
            ]
        )

        call_command("ingest_pinbase_models", path=path)

        child.refresh_from_db()
        assert child.alias_of == right_parent

    def test_variant_of_clears_circular_reference(self, db):
        """When models.json flips the parent/child, alias_of is cleared on new parent."""
        # ingest_opdb heuristic wrongly made model_a the parent, model_b the child.
        model_a = MachineModel.objects.create(name="Model A (CE)", opdb_id="Gtest-Ma")
        model_b = MachineModel.objects.create(
            name="Model B (LE)", opdb_id="Gtest-Mb", alias_of=model_a
        )
        # models.json says B is the real parent, A is the variant.
        path = _write_models_json(
            [
                {"slug": "model-b-le", "opdb_id": "Gtest-Mb"},
                {
                    "slug": "model-a-ce",
                    "opdb_id": "Gtest-Ma",
                    "variant_of": "model-b-le",
                },
            ]
        )

        call_command("ingest_pinbase_models", path=path)

        model_a.refresh_from_db()
        model_b.refresh_from_db()
        # B is the parent (alias_of cleared), A points to B.
        assert model_b.alias_of is None
        assert model_a.alias_of == model_b
