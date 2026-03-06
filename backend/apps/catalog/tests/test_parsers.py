"""Unit tests for ingestion parsers — pure functions, no database."""

from apps.catalog.ingestion.parsers import (
    map_opdb_display,
    map_opdb_type,
    parse_credit_string,
    parse_ipdb_date,
    parse_ipdb_location,
    parse_ipdb_machine_type,
    parse_ipdb_manufacturer_string,
    parse_opdb_date,
)


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
