"""Unit tests for ingestion parsers — pure functions, no database."""

import pytest

from apps.catalog.ingestion.parsers import (
    _IPDBLocationLookup,
    get_ipdb_location,
    map_opdb_display,
    map_opdb_type,
    parse_credit_string,
    parse_ipdb_date,
    parse_ipdb_location,
    parse_ipdb_machine_type,
    parse_ipdb_manufacturer_string,
    parse_opdb_date,
)
from apps.catalog.models import Location, LocationAlias


class TestParseIpdbDate:
    def test_full_date(self):
        assert parse_ipdb_date("1992-03-01T00:00:00") == (1992, 3)

    def test_year_only_placeholder(self):
        # IPDB uses Jan 1 as placeholder when only year is known.
        assert parse_ipdb_date("1997-01-01T00:00:00") == (1997, None)

    def test_none(self):
        assert parse_ipdb_date(None) == (None, None)

    def test_empty(self):
        assert parse_ipdb_date("") == (None, None)

    def test_invalid(self):
        assert parse_ipdb_date("not-a-date") == (None, None)

    def test_january_manufacture(self):
        # A machine actually manufactured in January but not on Jan 1.
        assert parse_ipdb_date("1992-01-15T00:00:00") == (1992, 1)


class TestParseOpdbDate:
    def test_full_date(self):
        assert parse_opdb_date("1992-03-01") == (1992, 3)

    def test_none(self):
        assert parse_opdb_date(None) == (None, None)

    def test_empty(self):
        assert parse_opdb_date("") == (None, None)


class TestParseIpdbMachineType:
    def test_em(self):
        assert parse_ipdb_machine_type("EM") == "electromechanical"

    def test_ss(self):
        assert parse_ipdb_machine_type("SS") == "solid-state"

    def test_none(self):
        assert parse_ipdb_machine_type(None) == ""

    def test_unknown(self):
        assert parse_ipdb_machine_type("XX") == ""

    def test_pure_mechanical_from_type_full(self):
        assert parse_ipdb_machine_type(None, "Pure Mechanical") == "pure-mechanical"

    def test_pure_mechanical_from_type_full_empty_short(self):
        assert parse_ipdb_machine_type("", "Pure Mechanical") == "pure-mechanical"

    def test_type_short_takes_precedence(self):
        assert parse_ipdb_machine_type("SS", "Pure Mechanical") == "solid-state"


class TestParseIpdbManufacturerString:
    def test_full_string(self):
        result = parse_ipdb_manufacturer_string(
            "D. Gottlieb & Company, of Chicago, Illinois (1931-1977) [Trade Name: Gottlieb]"
        )
        assert result["company_name"] == "D. Gottlieb & Company"
        assert result["trade_name"] == "Gottlieb"
        assert result["years_active"] == "1931-1977"
        assert result["location"] == "Chicago, Illinois"

    def test_no_trade_name(self):
        result = parse_ipdb_manufacturer_string(
            "A. J. Stephens and Company, of Kansas City, Missouri, USA (1932)"
        )
        assert result["company_name"] == "A. J. Stephens and Company"
        assert result["trade_name"] == ""
        assert result["years_active"] == "1932"

    def test_no_location(self):
        result = parse_ipdb_manufacturer_string(
            "Hankin (1978-1981) [Trade Name: Hankin]"
        )
        assert result["company_name"] == "Hankin"
        assert result["trade_name"] == "Hankin"

    def test_none(self):
        result = parse_ipdb_manufacturer_string(None)
        assert result["company_name"] == ""
        assert result["trade_name"] == ""
        assert result["years_active"] == ""

    def test_empty(self):
        result = parse_ipdb_manufacturer_string("")
        assert result["company_name"] == ""


class TestParseCreditString:
    def test_single_name(self):
        assert parse_credit_string("Pat Lawlor") == ["Pat Lawlor"]

    def test_multiple_names(self):
        assert parse_credit_string("Larry DeMar, Pat Lawlor") == [
            "Larry DeMar",
            "Pat Lawlor",
        ]

    def test_strips_parentheticals(self):
        assert parse_credit_string("Steve Ritchie (aka Doane)") == ["Steve Ritchie"]

    def test_skips_undisclosed(self):
        assert parse_credit_string("(Undisclosed)") == []

    def test_none(self):
        assert parse_credit_string(None) == []

    def test_empty(self):
        assert parse_credit_string("") == []

    def test_mixed(self):
        result = parse_credit_string("John Smith, (Unknown), Jane Doe (Jr.)")
        assert result == ["John Smith", "Jane Doe"]


class TestMapOpdbType:
    def test_em(self):
        assert map_opdb_type("em") == "electromechanical"

    def test_ss(self):
        assert map_opdb_type("ss") == "solid-state"

    def test_me(self):
        assert map_opdb_type("me") == "pure-mechanical"

    def test_empty(self):
        assert map_opdb_type("") == ""

    def test_none(self):
        assert map_opdb_type(None) == ""


class TestMapOpdbDisplay:
    def test_reels(self):
        assert map_opdb_display("reels") == "score-reels"

    def test_alphanumeric(self):
        assert map_opdb_display("alphanumeric") == "alphanumeric"

    def test_dmd(self):
        assert map_opdb_display("dmd") == "dot-matrix"

    def test_lcd(self):
        assert map_opdb_display("lcd") == "lcd"

    def test_cga(self):
        assert map_opdb_display("cga") == "cga"

    def test_lights(self):
        assert map_opdb_display("lights") == "backglass-lights"

    def test_empty(self):
        assert map_opdb_display("") == ""

    def test_none(self):
        assert map_opdb_display(None) == ""


class TestParseIpdbLocation:
    def test_us_city_state(self):
        result = parse_ipdb_location("Chicago, Illinois")
        assert result == {"city": "Chicago", "state": "Illinois", "country": "USA"}

    def test_three_parts(self):
        result = parse_ipdb_location("Chicago, Illinois, USA")
        assert result == {"city": "Chicago", "state": "Illinois", "country": "USA"}

    def test_non_us_two_parts(self):
        result = parse_ipdb_location("Bologna, Italy")
        assert result == {"city": "Bologna", "state": "", "country": "Italy"}

    def test_single_us_state(self):
        result = parse_ipdb_location("Illinois")
        assert result == {"city": "", "state": "Illinois", "country": "USA"}

    def test_single_non_us(self):
        result = parse_ipdb_location("Germany")
        assert result == {"city": "", "state": "", "country": "Germany"}

    def test_empty(self):
        result = parse_ipdb_location("")
        assert result == {"city": "", "state": "", "country": ""}

    # Country normalization
    def test_england_normalized_to_united_kingdom(self):
        result = parse_ipdb_location("London, England")
        assert result == {"city": "London", "state": "", "country": "United Kingdom"}

    def test_britain_normalized(self):
        result = parse_ipdb_location("Britain")
        assert result == {"city": "", "state": "", "country": "United Kingdom"}

    def test_uk_normalized(self):
        result = parse_ipdb_location("London, UK")
        assert result == {"city": "London", "state": "", "country": "United Kingdom"}

    def test_holland_normalized(self):
        result = parse_ipdb_location("Tilburg, Holland")
        assert result == {"city": "Tilburg", "state": "", "country": "Netherlands"}

    def test_west_germany_normalized(self):
        result = parse_ipdb_location("Bochum, West Germany")
        assert result == {"city": "Bochum", "state": "", "country": "Germany"}

    def test_the_netherlands_normalized(self):
        result = parse_ipdb_location("Reuver, The Netherlands")
        assert result == {"city": "Reuver", "state": "", "country": "Netherlands"}

    def test_roc_normalized(self):
        result = parse_ipdb_location("Kaohsiung City, Taiwan, R.O.C.")
        assert result == {
            "city": "Kaohsiung City",
            "state": "Taiwan",
            "country": "Taiwan",
        }

    # State normalization
    def test_newyork_typo_normalized(self):
        result = parse_ipdb_location("Elmira, NewYork")
        assert result == {"city": "Elmira", "state": "New York", "country": "USA"}

    def test_southcarolina_typo_normalized(self):
        result = parse_ipdb_location("Greenville, SouthCarolina")
        assert result == {
            "city": "Greenville",
            "state": "South Carolina",
            "country": "USA",
        }

    def test_scotland_normalized_to_united_kingdom(self):
        result = parse_ipdb_location("Edinburgh, Scotland")
        assert result == {"city": "Edinburgh", "state": "", "country": "United Kingdom"}

    def test_wales_normalized_to_united_kingdom(self):
        result = parse_ipdb_location("Cardiff, Wales")
        assert result == {"city": "Cardiff", "state": "", "country": "United Kingdom"}

    # Three-part with normalization
    def test_three_parts_with_country_normalization(self):
        result = parse_ipdb_location("Cardiff, Wales, UK")
        assert result == {
            "city": "Cardiff",
            "state": "Wales",
            "country": "United Kingdom",
        }

    # Parenthetical stripping
    def test_strips_parenthetical_years(self):
        result = parse_ipdb_location("Jersey City, New Jersey, USA (0-1925)")
        assert result == {
            "city": "Jersey City",
            "state": "New Jersey",
            "country": "USA",
        }

    def test_strips_parenthetical_years_two_part(self):
        result = parse_ipdb_location("New York, New York (0-0)")
        assert result == {"city": "New York", "state": "New York", "country": "USA"}


def _make_location(location_path, name, location_type, parent=None):
    slug = location_path.rsplit("/", 1)[-1]
    return Location.objects.create(
        location_path=location_path,
        slug=slug,
        name=name,
        location_type=location_type,
        parent=parent,
    )


class TestIPDBLocationLookup:
    @pytest.fixture()
    def loc_tree(self, db):
        usa = _make_location("usa", "USA", "country")
        il = _make_location("usa/il", "Illinois", "state", parent=usa)
        chicago = _make_location("usa/il/chicago", "Chicago", "city", parent=il)
        nl = _make_location("netherlands", "Netherlands", "country")
        reuver = _make_location("netherlands/reuver", "Reuver", "city", parent=nl)
        italy = _make_location("italy", "Italy", "country")
        bo = _make_location("italy/bo", "Bologna Province", "province", parent=italy)
        bologna = _make_location("italy/bo/bologna", "Bologna", "city", parent=bo)
        return {
            "usa": usa,
            "il": il,
            "chicago": chicago,
            "nl": nl,
            "reuver": reuver,
            "italy": italy,
            "bo": bo,
            "bologna": bologna,
        }

    def test_us_city_state_country(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert (
            lookup.resolve({"city": "Chicago", "state": "Illinois", "country": "USA"})
            == "usa/il/chicago"
        )

    def test_country_only(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert lookup.resolve({"city": "", "state": "", "country": "USA"}) == "usa"

    def test_state_no_city(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert (
            lookup.resolve({"city": "", "state": "Illinois", "country": "USA"})
            == "usa/il"
        )

    def test_city_direct_child_of_country(self, loc_tree):
        """Netherlands→Reuver has no subdivision; city is a direct child of country."""
        lookup = _IPDBLocationLookup()
        assert (
            lookup.resolve({"city": "Reuver", "state": "", "country": "Netherlands"})
            == "netherlands/reuver"
        )

    def test_city_deep_hierarchy(self, loc_tree):
        """Bologna is under Italy/Province; resolved via country-wide fallback."""
        lookup = _IPDBLocationLookup()
        assert (
            lookup.resolve({"city": "Bologna", "state": "", "country": "Italy"})
            == "italy/bo/bologna"
        )

    def test_alias_resolution(self, loc_tree):
        LocationAlias.objects.create(location=loc_tree["usa"], value="United States")
        lookup = _IPDBLocationLookup()
        assert (
            lookup.resolve({"city": "", "state": "", "country": "United States"})
            == "usa"
        )

    def test_unknown_country_returns_none(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert (
            lookup.resolve({"city": "Springfield", "state": "", "country": "Freedonia"})
            is None
        )

    def test_unknown_state_returns_none(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert (
            lookup.resolve(
                {"city": "Springfield", "state": "Freedonia", "country": "USA"}
            )
            is None
        )

    def test_empty_parsed_returns_none(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert lookup.resolve({"city": "", "state": "", "country": ""}) is None


class TestGetIpdbLocation:
    @pytest.fixture()
    def loc_tree(self, db):
        usa = _make_location("usa", "USA", "country")
        il = _make_location("usa/il", "Illinois", "state", parent=usa)
        _make_location("usa/il/chicago", "Chicago", "city", parent=il)
        ny = _make_location("usa/ny", "New York", "state", parent=usa)
        _make_location("usa/ny/long-island-city", "Long Island City", "city", parent=ny)
        spain = _make_location("spain", "Spain", "country")
        mad = _make_location("spain/mad", "Madrid Community", "community", parent=spain)
        madrid_prov = _make_location(
            "spain/mad/madrid", "Madrid", "province", parent=mad
        )
        _make_location("spain/mad/madrid/madrid", "Madrid", "city", parent=madrid_prov)

    def test_override_returns_path(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert get_ipdb_location(532, "Chicago Illinois", lookup) == "usa/il/chicago"

    def test_override_long_island_city(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert (
            get_ipdb_location(607, "Long Island City, Queens, New York", lookup)
            == "usa/ny/long-island-city"
        )

    def test_override_madrid_resolves_to_city(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert get_ipdb_location(439, "Madrid", lookup) == "spain/mad/madrid/madrid"

    def test_fallback_resolves_via_lookup(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert get_ipdb_location(999, "Chicago, Illinois", lookup) == "usa/il/chicago"

    def test_empty_location_returns_none(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert get_ipdb_location(999, "", lookup) is None

    def test_unresolvable_returns_none(self, loc_tree):
        lookup = _IPDBLocationLookup()
        assert get_ipdb_location(999, "Springfield, Freedonia", lookup) is None
