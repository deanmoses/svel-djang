"""Tests for model ingestion via ingest_pinbase command."""

import json
import os
import tempfile

import pytest
from django.core.management import call_command

from apps.catalog.models import MachineModel, Title
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
    """Write entries to a temp export dir and return the dir path."""
    export_dir = tempfile.mkdtemp()
    with open(os.path.join(export_dir, "model.json"), "w") as f:
        json.dump(entries, f)
    return export_dir


@pytest.mark.django_db
class TestIngestPinbaseModels:
    def test_creates_name_claim(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Foo (Limited Edition)"}]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="name", is_active=True)
        assert claim.value == "Foo (Limited Edition)"

    def test_pinbase_wins_resolution(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Foo (Limited Edition)"}]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        resolve_model(mm)
        mm.refresh_from_db()

        assert mm.name == "Foo (Limited Edition)"

    def test_skips_unknown_opdb_id(self, db):
        export_dir = _write_models_json(
            [{"opdb_id": "Gfake-Mfake", "name": "Nonexistent"}]
        )
        # Should not raise
        call_command("ingest_pinbase", export_dir=export_dir)

    def test_idempotent(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Foo (Limited Edition)"}]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        assert (
            mm.claims.filter(source=source, field_name="name", is_active=True).count()
            == 1
        )

    def test_description_claim(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [
                {
                    "opdb_id": "Gtest-Mtest",
                    "name": "Foo (Limited Edition)",
                    "description": "A test description",
                }
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="description", is_active=True)
        assert claim.value == "A test description"

    def test_display_type_claim(self, model_with_opdb_name_simple):
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [
                {
                    "opdb_id": "Gtest-Mtest",
                    "name": "Foo (Limited Edition)",
                    "display_type_slug": "alphanumeric",
                }
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="display_type", is_active=True)
        assert claim.value == "alphanumeric"

    def test_variant_of_claim(self, db):
        """variant_of asserts a claim with the slug value."""
        MachineModel.objects.create(
            name="Parent Model", opdb_id="Gtest-Mparent", slug="parent-model"
        )
        child = MachineModel.objects.create(
            name="Child Model", opdb_id="Gtest-Mchild", slug="child-model"
        )
        export_dir = _write_models_json(
            [
                {"slug": "parent-model", "opdb_id": "Gtest-Mparent"},
                {
                    "slug": "child-model",
                    "opdb_id": "Gtest-Mchild",
                    "variant_of": "parent-model",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        claim = child.claims.get(source=source, field_name="variant_of", is_active=True)
        assert claim.value == "parent-model"

    def test_variant_of_resolves(self, db):
        """variant_of slug claim resolves to FK on model."""
        parent = MachineModel.objects.create(
            name="Parent Model", opdb_id="Gtest-Mparent", slug="parent-model"
        )
        child = MachineModel.objects.create(
            name="Child Model", opdb_id="Gtest-Mchild", slug="child-model"
        )
        export_dir = _write_models_json(
            [
                {"slug": "parent-model", "opdb_id": "Gtest-Mparent"},
                {
                    "slug": "child-model",
                    "opdb_id": "Gtest-Mchild",
                    "variant_of": "parent-model",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        resolve_model(child)
        child.refresh_from_db()

        assert child.variant_of == parent

    def test_variant_of_overrides_ingest(self, db):
        """variant_of from pinbase overrides a wrong variant_of from ingest_opdb."""
        MachineModel.objects.create(name="Wrong Parent", opdb_id="Gtest-Mwrong")
        right_parent = MachineModel.objects.create(
            name="Right Parent", opdb_id="Gtest-Mright", slug="right-parent"
        )
        child = MachineModel.objects.create(
            name="Child",
            opdb_id="Gtest-Mchild",
            slug="child-model",
            variant_of=MachineModel.objects.get(opdb_id="Gtest-Mwrong"),
        )
        export_dir = _write_models_json(
            [
                {"slug": "right-parent", "opdb_id": "Gtest-Mright"},
                {
                    "slug": "child-model",
                    "opdb_id": "Gtest-Mchild",
                    "variant_of": "right-parent",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        resolve_model(child)
        child.refresh_from_db()

        assert child.variant_of == right_parent

    def test_variant_of_clears_circular_reference(self, db):
        """When models.json flips the parent/child, variant_of is cleared on new parent."""
        # ingest_opdb heuristic wrongly made model_a the parent, model_b the child.
        model_a = MachineModel.objects.create(
            name="Model A (CE)", opdb_id="Gtest-Ma", slug="model-a-ce"
        )
        model_b = MachineModel.objects.create(
            name="Model B (LE)",
            opdb_id="Gtest-Mb",
            slug="model-b-le",
            variant_of=model_a,
        )
        # models.json says B is the real parent, A is the variant.
        export_dir = _write_models_json(
            [
                {"slug": "model-b-le", "opdb_id": "Gtest-Mb"},
                {
                    "slug": "model-a-ce",
                    "opdb_id": "Gtest-Ma",
                    "variant_of": "model-b-le",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        # Resolution resets all FKs to None, then applies winners.
        # model_b has no variant_of claim, so it stays None.
        resolve_model(model_a)
        resolve_model(model_b)
        model_a.refresh_from_db()
        model_b.refresh_from_db()

        assert model_b.variant_of is None
        assert model_a.variant_of == model_b

    def test_is_conversion_claim(self, model_with_opdb_name_simple):
        """is_conversion: true asserts a claim."""
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Dark Rider", "is_conversion": True}]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="is_conversion", is_active=True)
        assert claim.value is True

    def test_converted_from_claim(self, db):
        """converted_from asserts a claim with the slug value."""
        MachineModel.objects.create(
            name="Star Trek", opdb_id="Gtest-Msrc", slug="star-trek"
        )
        conv_mm = MachineModel.objects.create(
            name="Dark Rider", opdb_id="Gtest-Mconv", slug="dark-rider"
        )
        export_dir = _write_models_json(
            [
                {"slug": "star-trek", "opdb_id": "Gtest-Msrc", "name": "Star Trek"},
                {
                    "slug": "dark-rider",
                    "opdb_id": "Gtest-Mconv",
                    "name": "Dark Rider",
                    "is_conversion": True,
                    "converted_from": "star-trek",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        claim = conv_mm.claims.get(
            source=source, field_name="converted_from", is_active=True
        )
        assert claim.value == "star-trek"

    def test_is_conversion_resolves(self, model_with_opdb_name_simple):
        """is_conversion claim resolves to boolean on model."""
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Dark Rider", "is_conversion": True}]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        resolve_model(mm)
        mm.refresh_from_db()

        assert mm.is_conversion is True

    def test_converted_from_resolves(self, db):
        """converted_from slug claim resolves to FK on model."""
        source_mm = MachineModel.objects.create(
            name="Star Trek", opdb_id="Gtest-Msrc", slug="star-trek"
        )
        conv_mm = MachineModel.objects.create(
            name="Dark Rider", opdb_id="Gtest-Mconv", slug="dark-rider"
        )
        export_dir = _write_models_json(
            [
                {"slug": "star-trek", "opdb_id": "Gtest-Msrc", "name": "Star Trek"},
                {
                    "slug": "dark-rider",
                    "opdb_id": "Gtest-Mconv",
                    "name": "Dark Rider",
                    "is_conversion": True,
                    "converted_from": "star-trek",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        resolve_model(conv_mm)
        conv_mm.refresh_from_db()

        assert conv_mm.converted_from == source_mm
        assert conv_mm.is_conversion is True

    def test_is_conversion_without_source(self, model_with_opdb_name_simple):
        """is_conversion without converted_from only asserts is_conversion claim."""
        mm = model_with_opdb_name_simple
        export_dir = _write_models_json(
            [{"opdb_id": "Gtest-Mtest", "name": "Mystery Conv", "is_conversion": True}]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        assert mm.claims.filter(
            source=source, field_name="is_conversion", is_active=True
        ).exists()
        assert not mm.claims.filter(
            source=source, field_name="converted_from", is_active=True
        ).exists()

    def test_title_claim(self, db):
        """title asserts a claim with the slug value."""
        Title.objects.create(name="Test Title", slug="test-title", opdb_id="Gtest")
        mm = MachineModel.objects.create(
            name="Test Model", opdb_id="Gtest-Mtest", slug="test-model"
        )
        export_dir = _write_models_json(
            [
                {
                    "slug": "test-model",
                    "opdb_id": "Gtest-Mtest",
                    "title_slug": "test-title",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)

        source = Source.objects.get(slug="pinbase")
        claim = mm.claims.get(source=source, field_name="title", is_active=True)
        assert claim.value == "test-title"

    def test_title_resolves(self, db):
        """title slug claim resolves to FK on model."""
        title = Title.objects.create(
            name="Test Title", slug="test-title", opdb_id="Gtest"
        )
        mm = MachineModel.objects.create(
            name="Test Model", opdb_id="Gtest-Mtest", slug="test-model"
        )
        export_dir = _write_models_json(
            [
                {
                    "slug": "test-model",
                    "opdb_id": "Gtest-Mtest",
                    "title_slug": "test-title",
                },
            ]
        )

        call_command("ingest_pinbase", export_dir=export_dir)
        resolve_model(mm)
        mm.refresh_from_db()

        assert mm.title == title
