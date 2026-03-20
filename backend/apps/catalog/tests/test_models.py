import pytest
from django.db import IntegrityError

from apps.catalog.models import (
    CorporateEntity,
    Credit,
    CreditRole,
    Manufacturer,
    Person,
    MachineModel,
)
from apps.provenance.models import Claim, Source


@pytest.fixture
def source(db):
    return Source.objects.create(name="IPDB", source_type="database", priority=10)


@pytest.fixture
def editorial_source(db):
    return Source.objects.create(
        name="The Flip Editorial", source_type="editorial", priority=100
    )


@pytest.fixture
def manufacturer(db):
    return Manufacturer.objects.create(name="Williams")


@pytest.fixture
def corporate_entity(db, manufacturer):
    return CorporateEntity.objects.create(
        name="Williams Electronics", manufacturer=manufacturer
    )


@pytest.fixture
def machine_model(db, corporate_entity):
    return MachineModel.objects.create(
        name="Medieval Madness", corporate_entity=corporate_entity, year=1997
    )


@pytest.fixture
def person(db):
    return Person.objects.create(name="Brian Eddy")


# --- Source ---


class TestSource:
    def test_auto_slug(self, source):
        assert source.slug == "ipdb"

    def test_str(self, source):
        assert str(source) == "IPDB"

    def test_unique_name(self, db, source):
        with pytest.raises(IntegrityError):
            Source.objects.create(name="IPDB")


# --- Manufacturer ---


class TestManufacturer:
    def test_auto_slug(self, manufacturer):
        assert manufacturer.slug == "williams"

    def test_str(self, manufacturer):
        assert str(manufacturer) == "Williams"

    def test_slug_deduplication(self, db, manufacturer):
        # "Williams!" slugifies to "williams" which collides with the fixture.
        mfr2 = Manufacturer.objects.create(name="Williams!")
        assert mfr2.slug == "williams-2"


# --- CorporateEntity ---


class TestCorporateEntity:
    def test_create(self, manufacturer):
        entity = CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Manufacturing Company",
            slug="williams-mfg",
            year_start=1943,
            year_end=1985,
        )
        assert entity.manufacturer == manufacturer

    def test_str_with_years(self, manufacturer):
        entity = CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Manufacturing Company",
            slug="williams-mfg",
            year_start=1943,
            year_end=1985,
        )
        assert "Williams Manufacturing Company" in str(entity)
        assert "1943" in str(entity)
        assert "1985" in str(entity)

    def test_str_without_years(self, manufacturer):
        entity = CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Manufacturing Company",
            slug="williams-mfg",
        )
        assert str(entity) == "Williams Manufacturing Company"

    def test_multiple_entities_per_brand(self, manufacturer):
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Manufacturing Company",
            slug="williams-mfg",
            year_start=1943,
            year_end=1985,
        )
        CorporateEntity.objects.create(
            manufacturer=manufacturer,
            name="Williams Electronics",
            slug="williams-elec",
            year_start=1985,
            year_end=1999,
        )
        assert manufacturer.entities.count() == 2


# --- MachineModel ---


class TestMachineModel:
    def test_auto_slug_with_corporate_entity_year(self, machine_model):
        assert machine_model.slug == "medieval-madness-williams-electronics-1997"

    def test_auto_slug_without_corporate_entity(self, db):
        pm = MachineModel.objects.create(name="Test Game")
        assert pm.slug == "test-game"

    def test_str(self, machine_model):
        assert "Medieval Madness" in str(machine_model)
        assert "Williams Electronics" in str(machine_model)
        assert "1997" in str(machine_model)

    def test_slug_deduplication(self, db, corporate_entity, machine_model):
        pm2 = MachineModel.objects.create(
            name="Medieval Madness", corporate_entity=corporate_entity, year=1997
        )
        assert pm2.slug == "medieval-madness-williams-electronics-1997-2"


# --- Person ---


class TestPerson:
    def test_auto_slug(self, person):
        assert person.slug == "brian-eddy"

    def test_str(self, person):
        assert str(person) == "Brian Eddy"

    def test_slug_deduplication(self, db, person):
        p2 = Person.objects.create(name="Brian Eddy")
        assert p2.slug == "brian-eddy-2"


# --- Credit ---


class TestCredit:
    def test_create(self, machine_model, person, credit_roles):
        role = CreditRole.objects.get(slug="design")
        credit = Credit.objects.create(model=machine_model, person=person, role=role)
        assert "Brian Eddy" in str(credit)
        assert "Design" in str(credit)

    def test_unique_constraint(self, machine_model, person, credit_roles):
        role = CreditRole.objects.get(slug="design")
        Credit.objects.create(model=machine_model, person=person, role=role)
        with pytest.raises(IntegrityError):
            Credit.objects.create(model=machine_model, person=person, role=role)

    def test_different_roles_ok(self, machine_model, person, credit_roles):
        design = CreditRole.objects.get(slug="design")
        concept = CreditRole.objects.get(slug="concept")
        Credit.objects.create(model=machine_model, person=person, role=design)
        Credit.objects.create(model=machine_model, person=person, role=concept)
        assert machine_model.credits.count() == 2


# --- Claim ---


class TestClaim:
    def test_assert_claim_creates(self, machine_model, source):
        claim = Claim.objects.assert_claim(
            machine_model, "name", "Medieval Madness", source=source
        )
        assert claim.is_active is True
        assert claim.value == "Medieval Madness"

    def test_assert_claim_supersedes(self, machine_model, source):
        c1 = Claim.objects.assert_claim(machine_model, "year", 1997, source=source)
        c2 = Claim.objects.assert_claim(machine_model, "year", 1998, source=source)
        c1.refresh_from_db()
        assert c1.is_active is False
        assert c2.is_active is True

    def test_assert_claim_different_sources_coexist(
        self, machine_model, source, editorial_source
    ):
        c1 = Claim.objects.assert_claim(machine_model, "year", 1997, source=source)
        c2 = Claim.objects.assert_claim(
            machine_model, "year", 1997, source=editorial_source
        )
        c1.refresh_from_db()
        assert c1.is_active is True
        assert c2.is_active is True

    def test_unique_active_constraint(self, machine_model, source):
        from django.contrib.contenttypes.models import ContentType

        Claim.objects.assert_claim(machine_model, "name", "V1", source=source)
        ct = ContentType.objects.get_for_model(machine_model)
        # Direct create (bypassing manager) should violate the constraint
        # (keyed on claim_key, which equals field_name for scalar claims).
        with pytest.raises(IntegrityError):
            Claim.objects.create(
                content_type=ct,
                object_id=machine_model.pk,
                source=source,
                field_name="name",
                claim_key="name",
                value="V2",
                is_active=True,
            )

    def test_str(self, machine_model, source):
        claim = Claim.objects.assert_claim(machine_model, "year", 1997, source=source)
        assert "IPDB" in str(claim)
        assert "year" in str(claim)
