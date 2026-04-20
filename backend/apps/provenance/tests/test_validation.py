"""Tests for provenance.validation — claim-boundary validation."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import (
    CorporateEntity,
    Location,
    MachineModel,
    Manufacturer,
    Person,
    System,
    Theme,
    Title,
)
from apps.provenance.models import Claim, Source
from apps.provenance.validation import (
    DIRECT,
    EXTRA,
    RELATIONSHIP,
    UNRECOGNIZED,
    classify_claim,
    validate_claim_value,
    validate_claims_batch,
    validate_fk_claims_batch,
    validate_relationship_claims_batch,
)
from apps.catalog.tests.conftest import make_machine_model


# ---------------------------------------------------------------------------
# validate_claim_value
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateClaimValue:
    def test_valid_string_passes(self):
        result = validate_claim_value("name", "Eight Ball Deluxe", MachineModel)
        assert result == "Eight Ball Deluxe"

    def test_valid_integer_passes(self):
        # ipdb_id has MinValueValidator(1)
        result = validate_claim_value("ipdb_id", 42, MachineModel)
        assert result == 42

    def test_out_of_range_integer_rejected(self):
        # ipdb_id has MinValueValidator(1), so 0 should fail
        with pytest.raises(ValidationError):
            validate_claim_value("ipdb_id", 0, MachineModel)

    def test_invalid_type_coercion_rejected(self):
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_claim_value("ipdb_id", "not-a-number", MachineModel)

    def test_mojibake_rejected(self):
        # Mojibake: "Ã©" is é misinterpreted through cp1252
        with pytest.raises(ValidationError, match="mojibake"):
            validate_claim_value("name", "Caf\u00c3\u00a9", Person)

    def test_valid_accented_passes(self):
        result = validate_claim_value("name", "Café", Person)
        assert result == "Café"

    def test_whitespace_only_rejected_for_required_field(self):
        with pytest.raises(ValidationError, match="cannot be blank"):
            validate_claim_value("name", "   ", MachineModel)

    def test_whitespace_only_allowed_for_blank_field(self):
        # production_quantity is blank=True — whitespace-only is fine
        result = validate_claim_value("production_quantity", "   ", MachineModel)
        assert result == "   "

    def test_empty_string_skips_validators(self):
        # Empty string is the sentinel for "clear this field". Should not run
        # validators (which would reject "" as out of range for ipdb_id).
        result = validate_claim_value("ipdb_id", "", MachineModel)
        assert result == ""

    def test_float_decimal_field_not_rejected(self):
        # JSON has no Decimal type — values arrive as float. Ensure float 8.95
        # is not rejected by DecimalValidator due to IEEE 754 artifacts.
        result = validate_claim_value("ipdb_rating", 8.95, MachineModel)
        assert result == 8.95

    def test_fk_field_passes_through(self):
        # System.manufacturer is a FK to Manufacturer — should return unchanged.
        result = validate_claim_value("manufacturer", "some-slug", System)
        assert result == "some-slug"

    def test_boolean_field_rejects_invalid_string(self):
        # BooleanField has no validators, but to_python() should still run
        # and reject non-boolean strings like "maybe".
        with pytest.raises(ValidationError):
            validate_claim_value("needs_review", "maybe", Title)

    def test_boolean_field_accepts_valid_value(self):
        result = validate_claim_value("needs_review", True, Title)
        assert result is True

    # --- Validators added by field audit (step 7) ---

    def test_wikidata_id_valid_format_passes(self):
        result = validate_claim_value("wikidata_id", "Q312897", Person)
        assert result == "Q312897"

    def test_wikidata_id_invalid_format_rejected(self):
        with pytest.raises(ValidationError, match="Wikidata ID"):
            validate_claim_value("wikidata_id", "WD312897", Person)

    def test_wikidata_id_bare_number_rejected(self):
        with pytest.raises(ValidationError, match="Wikidata ID"):
            validate_claim_value("wikidata_id", "312897", Person)

    def test_wikidata_id_manufacturer_valid_passes(self):
        result = validate_claim_value("wikidata_id", "Q180268", Manufacturer)
        assert result == "Q180268"

    def test_wikidata_id_manufacturer_invalid_rejected(self):
        with pytest.raises(ValidationError, match="Wikidata ID"):
            validate_claim_value("wikidata_id", "WD180268", Manufacturer)

    def test_opdb_manufacturer_id_zero_rejected(self):
        with pytest.raises(ValidationError):
            validate_claim_value("opdb_manufacturer_id", 0, Manufacturer)

    def test_opdb_manufacturer_id_valid_passes(self):
        result = validate_claim_value("opdb_manufacturer_id", 7, Manufacturer)
        assert result == 7

    def test_ipdb_manufacturer_id_zero_rejected(self):
        with pytest.raises(ValidationError):
            validate_claim_value("ipdb_manufacturer_id", 0, CorporateEntity)

    def test_fandom_page_id_zero_rejected(self):
        with pytest.raises(ValidationError):
            validate_claim_value("fandom_page_id", 0, Title)

    def test_fandom_page_id_valid_passes(self):
        result = validate_claim_value("fandom_page_id", 42, Title)
        assert result == 42

    def test_production_quantity_mojibake_rejected(self):
        with pytest.raises(ValidationError, match="mojibake"):
            validate_claim_value("production_quantity", "Caf\u00c3\u00a9", MachineModel)

    def test_birth_place_mojibake_rejected(self):
        with pytest.raises(ValidationError, match="mojibake"):
            validate_claim_value("birth_place", "Caf\u00c3\u00a9", Person)

    def test_location_description_mojibake_rejected(self):
        with pytest.raises(ValidationError, match="mojibake"):
            validate_claim_value("description", "Caf\u00c3\u00a9", Location)


# ---------------------------------------------------------------------------
# validate_claims_batch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateClaimsBatch:
    @pytest.fixture
    def manufacturer(self):
        return Manufacturer.objects.create(name="Williams", slug="williams")

    @pytest.fixture
    def system(self, manufacturer):
        return System.objects.create(name="WPC", slug="wpc", manufacturer=manufacturer)

    @pytest.fixture
    def model(self):
        return make_machine_model(name="Eight Ball", slug="eight-ball")

    def test_valid_scalar_claim_passes(self, model):
        claim = Claim.for_object(model, field_name="name", value="Eight Ball Deluxe")
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1
        assert valid[0].value == "Eight Ball Deluxe"

    def test_invalid_scalar_claim_rejected(self, model):
        claim = Claim.for_object(model, field_name="ipdb_id", value="not-a-number")
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 1
        assert len(valid) == 0

    def test_mixed_valid_and_invalid(self, model):
        good = Claim.for_object(model, field_name="name", value="Good Name")
        bad = Claim.for_object(model, field_name="ipdb_id", value="bad")
        valid, rejected = validate_claims_batch([good, bad])
        assert rejected == 1
        assert len(valid) == 1
        assert valid[0].field_name == "name"

    def test_relationship_with_valid_targets_passes(self, model, credit_targets):
        pat_pk = credit_targets["persons"]["pat-lawlor"].pk
        design_pk = credit_targets["roles"]["design"].pk
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={"person": pat_pk, "role": design_pk, "exists": True},
            claim_key=f"credit|person:{pat_pk}|role:{design_pk}",
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_extra_data_claim_passes_through(self, model):
        claim = Claim.for_object(
            model, field_name="opdb.description", value="A great game"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_unrecognized_field_name_rejected(self):
        # Use Theme which has no extra_data fallback — unknown fields are rejected.
        theme = Theme.objects.create(name="Medieval", slug="medieval")
        claim = Claim.for_object(
            theme, field_name="nonexistent_field", value="whatever"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 1
        assert len(valid) == 0

    def test_unknown_field_on_extra_data_model_passes(self, model):
        # MachineModel has extra_data — unknown fields resolve into it.
        claim = Claim.for_object(
            model, field_name="nonexistent_field", value="whatever"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_fk_claim_with_valid_target(self, system, manufacturer):
        claim = Claim.for_object(
            system, field_name="manufacturer", value=manufacturer.slug
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_fk_claim_with_nonexistent_target(self, system):
        claim = Claim.for_object(
            system, field_name="manufacturer", value="no-such-manufacturer"
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 1
        assert len(valid) == 0

    def test_fk_claim_with_empty_value_passes(self, system):
        claim = Claim.for_object(system, field_name="manufacturer", value="")
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1


# ---------------------------------------------------------------------------
# validate_fk_claims_batch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateFkClaimsBatch:
    @pytest.fixture
    def manufacturer(self):
        return Manufacturer.objects.create(name="Williams", slug="williams")

    @pytest.fixture
    def system(self, manufacturer):
        return System.objects.create(name="WPC", slug="wpc", manufacturer=manufacturer)

    def test_valid_fk_passes(self, system, manufacturer):
        claim = Claim.for_object(
            system, field_name="manufacturer", value=manufacturer.slug
        )
        rejected = validate_fk_claims_batch([(claim, System)])
        assert rejected == []

    def test_invalid_fk_rejected(self, system):
        claim = Claim.for_object(
            system, field_name="manufacturer", value="no-such-slug"
        )
        rejected = validate_fk_claims_batch([(claim, System)])
        assert len(rejected) == 1

    def test_empty_value_not_rejected(self, system):
        claim = Claim.for_object(system, field_name="manufacturer", value="")
        rejected = validate_fk_claims_batch([(claim, System)])
        assert rejected == []

    def test_batch_queries_once_per_group(
        self, system, manufacturer, django_assert_num_queries
    ):
        """Multiple claims for the same (model, field) should result in one query."""
        c1 = Claim.for_object(
            system, field_name="manufacturer", value=manufacturer.slug
        )
        c2 = Claim.for_object(system, field_name="manufacturer", value="nonexistent")
        with django_assert_num_queries(1):
            rejected = validate_fk_claims_batch(
                [
                    (c1, System),
                    (c2, System),
                ]
            )
        assert len(rejected) == 1


# ---------------------------------------------------------------------------
# classify_claim
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClassifyClaim:
    def test_scalar_field_is_direct(self):
        assert classify_claim(MachineModel, "name", "", "Test") == DIRECT

    def test_fk_field_is_direct(self):
        assert classify_claim(System, "manufacturer", "", "williams") == DIRECT

    def test_relationship_claim_detected(self):
        """Compound claim_key + dict value with 'exists' → RELATIONSHIP."""
        assert (
            classify_claim(
                MachineModel,
                "credit",
                "credit|person:1|role:2",
                {"person": 1, "role": 2, "exists": True},
            )
            == RELATIONSHIP
        )

    def test_extra_data_on_model_with_extra_data(self):
        """Unknown field on a model with extra_data → EXTRA."""
        assert classify_claim(MachineModel, "opdb.description", "", "text") == EXTRA

    def test_unrecognized_on_model_without_extra_data(self):
        """Unknown field on a model without extra_data → UNRECOGNIZED."""
        assert classify_claim(Theme, "nonexistent", "", "whatever") == UNRECOGNIZED

    def test_undotted_extra_data_on_model_with_extra_data(self):
        """Undotted unknown field on model with extra_data → EXTRA."""
        assert classify_claim(MachineModel, "manufacturer", "", "williams") == EXTRA

    def test_relationship_convention_enforced(self):
        """Every relationship namespace produces a RELATIONSHIP claim.

        This turns the structural convention into a tested invariant: if
        build_relationship_claim ever stops producing compound claim_key
        or dict values with 'exists', this test breaks.
        """
        from apps.catalog.claims import build_relationship_claim, get_all_namespace_keys

        # Build a minimal identity dict for each namespace.
        for namespace, keys in get_all_namespace_keys().items():
            identity = {key: "test-value" for key in keys}
            claim_key, value = build_relationship_claim(namespace, identity)

            # Determine a model class that hosts this namespace. For the
            # purpose of this test, the model doesn't matter — what matters
            # is that the claim_key/value structure classifies as RELATIONSHIP
            # on any model (since field_name won't be in get_claim_fields).
            result = classify_claim(MachineModel, namespace, claim_key, value)
            assert result == RELATIONSHIP, (
                f"Namespace {namespace!r} classified as {result!r}, expected RELATIONSHIP. "
                f"claim_key={claim_key!r}, value={value!r}"
            )


# ---------------------------------------------------------------------------
# assert_claim validation (B4)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssertClaimValidation:
    @pytest.fixture
    def source(self):
        return Source.objects.create(
            name="test-source", source_type="database", priority=10
        )

    def test_rejects_invalid_direct_claim(self, source):
        """assert_claim should reject invalid scalar values."""
        model = make_machine_model(name="Test", slug="test")
        with pytest.raises(ValidationError, match="must be an integer"):
            Claim.objects.assert_claim(model, "ipdb_id", "not-a-number", source=source)

    def test_allows_valid_direct_claim(self, source):
        model = make_machine_model(name="Test", slug="test")
        claim = Claim.objects.assert_claim(model, "ipdb_id", 42, source=source)
        assert claim.value == 42

    def test_allows_relationship_claim(self, source):
        """assert_claim accepts relationship claims (batch target validation is separate)."""
        model = make_machine_model(name="Test", slug="test")
        claim = Claim.objects.assert_claim(
            model,
            "credit",
            {"person": 1, "role": 2, "exists": True},
            source=source,
            claim_key="credit|person:1|role:2",
        )
        assert claim.field_name == "credit"

    def test_allows_extra_data_claim(self, source):
        """Extra-data claims should pass through without validation."""
        model = make_machine_model(name="Test", slug="test")
        claim = Claim.objects.assert_claim(
            model, "opdb.description", "A great game", source=source
        )
        assert claim.value == "A great game"

    def test_rejects_unrecognized_claim(self, source):
        """Unrecognized field on a model without extra_data is rejected."""
        theme = Theme.objects.create(name="Medieval", slug="medieval")
        with pytest.raises(ValueError, match="Unrecognized claim field_name"):
            Claim.objects.assert_claim(
                theme, "nonexistent_field", "whatever", source=source
            )


# ---------------------------------------------------------------------------
# validate_relationship_claims_batch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateRelationshipClaimsBatch:
    @pytest.fixture
    def model(self):
        return make_machine_model(name="Eight Ball", slug="eight-ball")

    @pytest.fixture
    def theme(self):
        return Theme.objects.create(name="Medieval", slug="medieval")

    def test_valid_credit_passes(self, model, credit_targets):
        pat_pk = credit_targets["persons"]["pat-lawlor"].pk
        design_pk = credit_targets["roles"]["design"].pk
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={"person": pat_pk, "role": design_pk, "exists": True},
            claim_key=f"credit|person:{pat_pk}|role:{design_pk}",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert rejected == []

    def test_nonexistent_person_rejected(self, model, credit_targets):
        design_pk = credit_targets["roles"]["design"].pk
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={
                "person": 99999,
                "role": design_pk,
                "exists": True,
            },
            claim_key=f"credit|person:99999|role:{design_pk}",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert len(rejected) == 1

    def test_nonexistent_role_rejected(self, model, credit_targets):
        pat_pk = credit_targets["persons"]["pat-lawlor"].pk
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={
                "person": pat_pk,
                "role": 99999,
                "exists": True,
            },
            claim_key=f"credit|person:{pat_pk}|role:99999",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert len(rejected) == 1

    def test_both_targets_invalid_rejects_once(self, model):
        """A credit with both person and role missing is rejected once, not twice."""
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={
                "person": 99998,
                "role": 99999,
                "exists": True,
            },
            claim_key="credit|person:99998|role:99999",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert len(rejected) == 1

    def test_valid_theme_passes(self, model, theme):
        claim = Claim.for_object(
            model,
            field_name="theme",
            value={"theme": theme.pk, "exists": True},
            claim_key=f"theme|theme:{theme.pk}",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert rejected == []

    def test_nonexistent_theme_rejected(self, model):
        claim = Claim.for_object(
            model,
            field_name="theme",
            value={"theme": 99999, "exists": True},
            claim_key="theme|theme:99999",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert len(rejected) == 1

    def test_retraction_with_nonexistent_target_passes(self, model):
        """exists=False retractions pass even when the target no longer exists."""
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={
                "person": 99998,
                "role": 99999,
                "exists": False,
            },
            claim_key="credit|person:99998|role:99999",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert rejected == []

    def test_alias_namespace_passes_through(self, model):
        """Alias namespaces are not registered — claims pass without checking."""
        claim = Claim.for_object(
            model,
            field_name="theme_alias",
            value={"alias_value": "anything", "exists": True},
            claim_key="theme_alias|alias:anything",
        )
        rejected = validate_relationship_claims_batch([claim])
        assert rejected == []

    def test_batch_queries_once_per_group(
        self, model, credit_targets, django_assert_num_queries
    ):
        """Multiple credit claims should batch into one Person + one CreditRole query."""
        steve = Person.objects.create(name="Steve Ritchie", slug="steve-ritchie")
        pat_pk = credit_targets["persons"]["pat-lawlor"].pk
        design_pk = credit_targets["roles"]["design"].pk
        c1 = Claim.for_object(
            model,
            field_name="credit",
            value={"person": pat_pk, "role": design_pk, "exists": True},
            claim_key=f"credit|person:{pat_pk}|role:{design_pk}",
        )
        c2 = Claim.for_object(
            model,
            field_name="credit",
            value={
                "person": steve.pk,
                "role": design_pk,
                "exists": True,
            },
            claim_key=f"credit|person:{steve.pk}|role:{design_pk}",
        )
        # 2 queries: one for Person PKs, one for CreditRole PKs.
        with django_assert_num_queries(2):
            rejected = validate_relationship_claims_batch([c1, c2])
        assert rejected == []


# ---------------------------------------------------------------------------
# validate_claims_batch — relationship integration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidateClaimsBatchRelationships:
    @pytest.fixture
    def model(self):
        return make_machine_model(name="Test", slug="test")

    def test_valid_relationship_passes_batch(self, model, credit_targets):
        pat_pk = credit_targets["persons"]["pat-lawlor"].pk
        design_pk = credit_targets["roles"]["design"].pk
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={"person": pat_pk, "role": design_pk, "exists": True},
            claim_key=f"credit|person:{pat_pk}|role:{design_pk}",
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 0
        assert len(valid) == 1

    def test_invalid_relationship_rejected_in_batch(self, model, credit_targets):
        design_pk = credit_targets["roles"]["design"].pk
        claim = Claim.for_object(
            model,
            field_name="credit",
            value={
                "person": 99999,
                "role": design_pk,
                "exists": True,
            },
            claim_key=f"credit|person:99999|role:{design_pk}",
        )
        valid, rejected = validate_claims_batch([claim])
        assert rejected == 1
        assert len(valid) == 0

    def test_mixed_scalar_and_relationship(self, model, credit_targets):
        pat_pk = credit_targets["persons"]["pat-lawlor"].pk
        design_pk = credit_targets["roles"]["design"].pk
        good_scalar = Claim.for_object(model, field_name="name", value="Good Name")
        good_rel = Claim.for_object(
            model,
            field_name="credit",
            value={"person": pat_pk, "role": design_pk, "exists": True},
            claim_key=f"credit|person:{pat_pk}|role:{design_pk}",
        )
        bad_rel = Claim.for_object(
            model,
            field_name="theme",
            value={"theme": 99999, "exists": True},
            claim_key="theme|theme:99999",
        )
        valid, rejected = validate_claims_batch([good_scalar, good_rel, bad_rel])
        assert rejected == 1
        assert len(valid) == 2
