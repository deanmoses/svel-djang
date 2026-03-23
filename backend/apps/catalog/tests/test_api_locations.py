from apps.catalog.models import Address, CorporateEntity, Manufacturer


def _setup_locations(db):
    """Create manufacturers with addresses across multiple locations."""
    williams = Manufacturer.objects.create(name="Williams")
    williams_entity = CorporateEntity.objects.create(
        name="Williams Electronics",
        slug="williams-electronics",
        manufacturer=williams,
    )
    Address.objects.create(
        corporate_entity=williams_entity,
        city="Chicago",
        state="Illinois",
        country="USA",
    )

    gottlieb = Manufacturer.objects.create(name="Gottlieb")
    gottlieb_entity = CorporateEntity.objects.create(
        name="D. Gottlieb & Co.",
        slug="d-gottlieb-co",
        manufacturer=gottlieb,
    )
    Address.objects.create(
        corporate_entity=gottlieb_entity,
        city="Chicago",
        state="Illinois",
        country="USA",
    )

    stern = Manufacturer.objects.create(name="Stern")
    stern_entity = CorporateEntity.objects.create(
        name="Stern Pinball, Inc.",
        slug="stern-pinball-inc",
        manufacturer=stern,
    )
    Address.objects.create(
        corporate_entity=stern_entity,
        city="Elk Grove Village",
        state="Illinois",
        country="USA",
    )

    # A manufacturer with a city but no state (e.g. Netherlands)
    dutch = Manufacturer.objects.create(name="Dutch Pinball")
    dutch_entity = CorporateEntity.objects.create(
        name="Dutch Pinball",
        slug="dutch-pinball",
        manufacturer=dutch,
    )
    Address.objects.create(
        corporate_entity=dutch_entity,
        city="Reuver",
        state="",
        country="Netherlands",
    )

    return williams, gottlieb, stern, dutch


class TestLocationsIndex:
    def test_lists_countries(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/")
        assert resp.status_code == 200
        data = resp.json()
        countries = data["countries"]
        names = [c["name"] for c in countries]
        assert "USA" in names
        assert "Netherlands" in names

    def test_country_has_manufacturer_count(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/")
        data = resp.json()
        usa = next(c for c in data["countries"] if c["slug"] == "usa")
        assert usa["manufacturer_count"] == 3

    def test_country_has_states(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/")
        data = resp.json()
        usa = next(c for c in data["countries"] if c["slug"] == "usa")
        assert len(usa["states"]) == 1
        assert usa["states"][0]["name"] == "Illinois"

    def test_stateless_cities_on_country(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/")
        data = resp.json()
        nl = next(c for c in data["countries"] if c["slug"] == "netherlands")
        assert nl["manufacturer_count"] == 1
        assert len(nl["states"]) == 0
        assert len(nl["cities"]) == 1
        assert nl["cities"][0]["name"] == "Reuver"


class TestCountryDetail:
    def test_returns_country(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "USA"
        assert data["manufacturer_count"] == 3

    def test_includes_manufacturers(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa")
        data = resp.json()
        mfr_names = {m["name"] for m in data["manufacturers"]}
        assert mfr_names == {"Williams", "Gottlieb", "Stern"}

    def test_includes_states_and_cities(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa")
        data = resp.json()
        assert len(data["states"]) == 1
        illinois = data["states"][0]
        assert illinois["name"] == "Illinois"
        assert illinois["manufacturer_count"] == 3
        city_names = {c["name"] for c in illinois["cities"]}
        assert "Chicago" in city_names
        assert "Elk Grove Village" in city_names

    def test_404_for_unknown_country(self, client, db):
        resp = client.get("/api/locations/atlantis")
        assert resp.status_code == 404

    def test_stateless_cities(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/netherlands")
        data = resp.json()
        assert len(data["cities"]) == 1
        assert data["cities"][0]["name"] == "Reuver"


class TestStateDetail:
    def test_returns_state(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa/illinois")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Illinois"
        assert data["country_name"] == "USA"
        assert data["country_slug"] == "usa"
        assert data["manufacturer_count"] == 3

    def test_includes_cities(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa/illinois")
        data = resp.json()
        city_names = {c["name"] for c in data["cities"]}
        assert "Chicago" in city_names
        assert "Elk Grove Village" in city_names

    def test_cities_sorted_by_manufacturer_count_then_name(self, client, db):
        alpha = Manufacturer.objects.create(name="Alpha Manufacturing")
        alpha_entity = CorporateEntity.objects.create(
            name="Alpha Manufacturing",
            slug="alpha-manufacturing",
            manufacturer=alpha,
        )
        Address.objects.create(
            corporate_entity=alpha_entity,
            city="Albany",
            state="Illinois",
            country="USA",
        )

        zeta_one = Manufacturer.objects.create(name="Zeta One")
        zeta_one_entity = CorporateEntity.objects.create(
            name="Zeta One",
            slug="zeta-one",
            manufacturer=zeta_one,
        )
        Address.objects.create(
            corporate_entity=zeta_one_entity,
            city="Zephyr",
            state="Illinois",
            country="USA",
        )

        zeta_two = Manufacturer.objects.create(name="Zeta Two")
        zeta_two_entity = CorporateEntity.objects.create(
            name="Zeta Two",
            slug="zeta-two",
            manufacturer=zeta_two,
        )
        Address.objects.create(
            corporate_entity=zeta_two_entity,
            city="Zephyr",
            state="Illinois",
            country="USA",
        )

        resp = client.get("/api/locations/usa/illinois")
        data = resp.json()

        assert [city["name"] for city in data["cities"]] == ["Zephyr", "Albany"]


class TestLocationsCacheInvalidation:
    def test_country_detail_refreshes_when_address_changes(self, client, db):
        _setup_locations(db)

        initial = client.get("/api/locations/usa")
        assert initial.status_code == 200
        assert initial.json()["manufacturer_count"] == 3

        williams_entity = CorporateEntity.objects.get(slug="williams-electronics")
        Address.objects.create(
            corporate_entity=williams_entity,
            city="Rockford",
            state="Illinois",
            country="USA",
        )

        refreshed = client.get("/api/locations/usa")
        data = refreshed.json()

        assert data["manufacturer_count"] == 3
        assert {city["name"] for city in data["states"][0]["cities"]} == {
            "Chicago",
            "Elk Grove Village",
            "Rockford",
        }

    def test_includes_manufacturers(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa/illinois")
        data = resp.json()
        mfr_names = {m["name"] for m in data["manufacturers"]}
        assert mfr_names == {"Williams", "Gottlieb", "Stern"}

    def test_404_for_unknown_state(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa/texas")
        assert resp.status_code == 404

    def test_404_for_unknown_country(self, client, db):
        resp = client.get("/api/locations/atlantis/illinois")
        assert resp.status_code == 404


class TestCityDetail:
    def test_returns_city_with_state(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa/illinois/chicago")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Chicago"
        assert data["state_name"] == "Illinois"
        assert data["state_slug"] == "illinois"
        assert data["country_name"] == "USA"
        assert data["manufacturer_count"] == 2

    def test_city_includes_correct_manufacturers(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa/illinois/chicago")
        data = resp.json()
        mfr_names = {m["name"] for m in data["manufacturers"]}
        assert mfr_names == {"Williams", "Gottlieb"}

    def test_404_for_unknown_city(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/usa/illinois/springfield")
        assert resp.status_code == 404


class TestStatelessCityDetail:
    def test_returns_city_without_state(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/netherlands/cities/reuver")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Reuver"
        assert data["state_name"] is None
        assert data["state_slug"] is None
        assert data["country_name"] == "Netherlands"
        assert data["manufacturer_count"] == 1

    def test_includes_manufacturer(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/netherlands/cities/reuver")
        data = resp.json()
        assert len(data["manufacturers"]) == 1
        assert data["manufacturers"][0]["name"] == "Dutch Pinball"

    def test_404_for_unknown_city(self, client, db):
        _setup_locations(db)
        resp = client.get("/api/locations/netherlands/cities/amsterdam")
        assert resp.status_code == 404
