"""Parsing utilities for IPDB and OPDB data ingestion."""

from __future__ import annotations

import re


def parse_ipdb_date(s: str | None) -> tuple[int | None, int | None]:
    """Parse IPDB datetime string like "1992-03-01T00:00:00" into (year, month).

    Returns (None, None) for empty or unparseable values.
    """
    if not s:
        return None, None
    match = re.match(r"(\d{4})-(\d{2})", s)
    if not match:
        return None, None
    year = int(match.group(1))
    month = int(match.group(2))
    # IPDB uses month=1 as a placeholder when only year is known.
    if month == 1 and s.endswith("01-01T00:00:00"):
        month = None
    return year, month


def parse_opdb_date(s: str | None) -> tuple[int | None, int | None]:
    """Parse OPDB date string like "1992-03-01" into (year, month).

    Returns (None, None) for empty or unparseable values.
    """
    if not s:
        return None, None
    match = re.match(r"(\d{4})-(\d{2})", s)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_ipdb_machine_type(
    type_short: str | None, type_full: str | None = None
) -> str:
    """Map IPDB TypeShortName (and full Type fallback) to a technology_generation slug.

    IPDB uses "EM" and "SS" in TypeShortName. Pure Mechanical machines have an
    empty TypeShortName but Type="Pure Mechanical".
    """
    if type_short:
        mapping = {"EM": "electromechanical", "SS": "solid-state"}
        result = mapping.get(type_short.strip(), "")
        if result:
            return result
    if type_full and "pure mechanical" in type_full.lower():
        return "pure-mechanical"
    return ""


def parse_ipdb_manufacturer_string(raw: str | None) -> dict[str, str]:
    """Parse IPDB Manufacturer string into components.

    Example input:
        "D. Gottlieb & Company, of Chicago, Illinois (1931-1977) [Trade Name: Gottlieb]"

    Returns dict with keys: company_name, trade_name, years_active, location.
    All values default to empty string if not found.
    """
    if not raw:
        return {
            "company_name": "",
            "trade_name": "",
            "years_active": "",
            "location": "",
        }

    # Extract trade name from [Trade Name: X]
    trade_match = re.search(r"\[Trade Name:\s*(.+?)\]", raw)
    trade_name = trade_match.group(1).strip() if trade_match else ""

    # Extract years from (YYYY-YYYY) or (YYYY-present) or (YYYY)
    years_match = re.search(r"\((\d{4}(?:-(?:\d{4}|present))?)\)", raw)
    years_active = years_match.group(1) if years_match else ""

    # Extract location from ", of ..." segment (before years/trade name bracket).
    location_match = re.search(r",\s*of\s+(.+?)(?:\s*\(\d{4}|\s*\[Trade|\s*$)", raw)
    location = location_match.group(1).strip().rstrip(",") if location_match else ""

    # Company name: text before ", of" or before "(" or before "["
    company = raw
    # Remove the trade name bracket
    company = re.sub(r"\s*\[Trade Name:.*?\]", "", company)
    # Remove years
    company = re.sub(r"\s*\(\d{4}.*?\)", "", company)
    # Remove location (", of ...")
    company = re.sub(r",\s*of\s+.*$", "", company)
    company = company.strip().rstrip(",")

    return {
        "company_name": company,
        "trade_name": trade_name,
        "years_active": years_active,
        "location": location,
    }


# US state names for disambiguating IPDB location parsing.
# Includes IPDB typo variants (e.g. "NewYork") so they're recognized as states.
_US_STATES = frozenset(
    {
        "Alabama",
        "Alaska",
        "Arizona",
        "Arkansas",
        "California",
        "Colorado",
        "Connecticut",
        "Delaware",
        "Florida",
        "Georgia",
        "Hawaii",
        "Idaho",
        "Illinois",
        "Indiana",
        "Iowa",
        "Kansas",
        "Kentucky",
        "Louisiana",
        "Maine",
        "Maryland",
        "Massachusetts",
        "Michigan",
        "Minnesota",
        "Mississippi",
        "Missouri",
        "Montana",
        "Nebraska",
        "Nevada",
        "New Hampshire",
        "New Jersey",
        "New Mexico",
        "New York",
        "North Carolina",
        "North Dakota",
        "Ohio",
        "Oklahoma",
        "Oregon",
        "Pennsylvania",
        "Rhode Island",
        "South Carolina",
        "South Dakota",
        "Tennessee",
        "Texas",
        "Utah",
        "Vermont",
        "Virginia",
        "Washington",
        "West Virginia",
        "Wisconsin",
        "Wyoming",
        # IPDB typos
        "NewYork",
        "SouthCarolina",
    }
)

# Canonical country names — every country that appears in the data must be here.
# Values from the normalization map are included automatically.
_KNOWN_COUNTRIES = frozenset(
    {
        "Argentina",
        "Australia",
        "Austria",
        "Belgium",
        "Brazil",
        "Canada",
        "China",
        "France",
        "Germany",
        "Italy",
        "Japan",
        "Netherlands",
        "New Zealand",
        "Portugal",
        "Russia",
        "Slovenia",
        "Spain",
        "Sweden",
        "Taiwan",
        "United Kingdom",
        "USA",
    }
)

# Canonical US state names (post-normalization) for validating US addresses.
_CANONICAL_US_STATES = frozenset(
    {
        "Alabama",
        "Alaska",
        "Arizona",
        "Arkansas",
        "California",
        "Colorado",
        "Connecticut",
        "D.C.",
        "Delaware",
        "Florida",
        "Georgia",
        "Hawaii",
        "Idaho",
        "Illinois",
        "Indiana",
        "Iowa",
        "Kansas",
        "Kentucky",
        "Louisiana",
        "Maine",
        "Maryland",
        "Massachusetts",
        "Michigan",
        "Minnesota",
        "Mississippi",
        "Missouri",
        "Montana",
        "Nebraska",
        "Nevada",
        "New Hampshire",
        "New Jersey",
        "New Mexico",
        "New York",
        "North Carolina",
        "North Dakota",
        "Ohio",
        "Oklahoma",
        "Oregon",
        "Pennsylvania",
        "Rhode Island",
        "South Carolina",
        "South Dakota",
        "Tennessee",
        "Texas",
        "Utah",
        "Vermont",
        "Virginia",
        "Washington",
        "West Virginia",
        "Wisconsin",
        "Wyoming",
    }
)

# Normalization maps ported from pinexplore/sql/01_reference.sql.
_COUNTRY_NORMALIZATION: dict[str, str] = {
    "England": "United Kingdom",
    "Britain": "United Kingdom",
    "UK": "United Kingdom",
    "U.K.": "United Kingdom",
    "West Germany": "Germany",
    "Holland": "Netherlands",
    "The Netherlands": "Netherlands",
    "R.O.C.": "Taiwan",
}

_STATE_NORMALIZATION: dict[str, str] = {
    "NewYork": "New York",
    "SouthCarolina": "South Carolina",
}

# Per-manufacturer-ID location overrides for IPDB records with malformed
# location strings (missing commas, multi-city HQs, etc.).
_IPDB_LOCATION_OVERRIDES: dict[int, dict[str, str]] = {
    532: {"city": "Chicago", "state": "Illinois", "country": "USA"},
    607: {"city": "Long Island City", "state": "New York", "country": "USA"},
    764: {"city": "Lincoln", "state": "Nebraska", "country": "USA"},
    696: {"city": "Youngstown", "state": "Ohio", "country": "USA"},
    439: {"city": "Madrid", "state": "", "country": "Spain"},
    364: {"city": "Marcoussis", "state": "", "country": "France"},
    135: {"city": "Avenza", "state": "", "country": "Italy"},
}


def _normalize_location(result: dict[str, str]) -> dict[str, str]:
    """Apply state and country normalization to a parsed location dict."""
    result["state"] = _STATE_NORMALIZATION.get(result["state"], result["state"])
    result["country"] = _COUNTRY_NORMALIZATION.get(result["country"], result["country"])
    return result


def parse_ipdb_location(location: str) -> dict[str, str]:
    """Parse an IPDB location string into city, state, country.

    Handles formats:
    - 3-part: "Chicago, Illinois, USA" → city/state/country
    - 2-part + US state: "Chicago, Illinois" → city/state/USA
    - 2-part non-US: "Bologna, Italy" → city/""/country
    - 1-part US state: "Illinois" → ""/state/USA
    - 1-part non-US: "Germany" → ""/""/country

    Strips parenthetical suffixes (e.g. years that leaked into location).
    Normalizes country and state names (e.g. "England" → "United Kingdom",
    "NewYork" → "New York").

    Returns dict with keys: city, state, country (all default to "").
    """
    if not location:
        return {"city": "", "state": "", "country": ""}

    # Strip parenthetical suffixes (e.g. "(0-1925)" years that leaked into location)
    location = re.sub(r"\s*\(.*?\)\s*$", "", location)

    parts = [p.strip() for p in location.split(",")]

    if len(parts) >= 3:
        return _normalize_location(
            {"city": parts[0], "state": parts[1], "country": parts[2]}
        )

    if len(parts) == 2:
        if parts[1] in _US_STATES:
            return _normalize_location(
                {"city": parts[0], "state": parts[1], "country": "USA"}
            )
        return _normalize_location({"city": parts[0], "state": "", "country": parts[1]})

    # Single part
    if parts[0] in _US_STATES:
        return _normalize_location({"city": "", "state": parts[0], "country": "USA"})
    return _normalize_location({"city": "", "state": "", "country": parts[0]})


class LocationValidationError(ValueError):
    """Raised when a parsed IPDB location contains unrecognized values."""


def _validate_location(result: dict[str, str], mfr_id: int, raw: str) -> None:
    """Validate a parsed location dict against known countries and states.

    Raises ``LocationValidationError`` for unrecognized values so the ingest
    fails loudly rather than silently storing bad data.
    """
    country = result["country"]
    state = result["state"]

    if country and country not in _KNOWN_COUNTRIES:
        raise LocationValidationError(
            f"IPDB manufacturer {mfr_id}: unknown country {country!r} "
            f"(from {raw!r}). Add it to _KNOWN_COUNTRIES in parsers.py, "
            f"or add a normalization mapping, or add an override."
        )

    if country == "USA" and state and state not in _CANONICAL_US_STATES:
        raise LocationValidationError(
            f"IPDB manufacturer {mfr_id}: unknown US state {state!r} "
            f"(from {raw!r}). Add it to _CANONICAL_US_STATES in parsers.py, "
            f"or add a normalization mapping, or add an override."
        )


def get_ipdb_location(mfr_id: int, location: str) -> dict[str, str]:
    """Get normalized location for an IPDB manufacturer.

    Checks per-manufacturer overrides first (for malformed IPDB strings),
    then falls back to ``parse_ipdb_location``.

    Raises ``LocationValidationError`` if the result contains an unrecognized
    country or US state.
    """
    override = _IPDB_LOCATION_OVERRIDES.get(mfr_id)
    if override is not None:
        return dict(override)
    result = parse_ipdb_location(location)
    _validate_location(result, mfr_id, location)
    return result


def parse_credit_string(raw: str | None) -> list[str]:
    """Split IPDB credit string into individual person names.

    Handles comma-separated names and strips parenthetical qualifiers
    like "(aka Doane)" or "(Undisclosed)".

    Returns empty list for empty input.
    """
    if not raw:
        return []
    # Split on comma
    parts = raw.split(",")
    names = []
    for part in parts:
        # Remove parentheticals
        name = re.sub(r"\s*\(.*?\)", "", part).strip()
        if not name:
            continue
        # Skip known non-names
        if name.lower() in ("undisclosed", "unknown", "n/a", "none"):
            continue
        names.append(name)
    return names


def map_opdb_type(t: str | None) -> str:
    """Map OPDB type string to a technology_generation slug."""
    if not t:
        return ""
    mapping = {"em": "electromechanical", "ss": "solid-state", "me": "pure-mechanical"}
    return mapping.get(t.strip().lower(), "")


def map_opdb_display(d: str | None) -> str:
    """Map OPDB display string to a display_type slug."""
    if not d:
        return ""
    mapping = {
        "reels": "score-reels",
        "alphanumeric": "alphanumeric",
        "dmd": "dot-matrix",
        "lcd": "lcd",
        "lights": "backglass-lights",
        "cga": "cga",
    }
    return mapping.get(d.strip().lower(), "")


def parse_opdb_group_id(opdb_id: str | None) -> str:
    """Extract the group prefix from an OPDB machine/alias ID.

    OPDB IDs follow the pattern G{group}-M{machine}[-A{alias}].
    The group prefix is the first segment (before the first '-').

    >>> parse_opdb_group_id("G5pe4-MkPy7")
    'G5pe4'
    >>> parse_opdb_group_id("G5pe4-MkPy7-AOPQR")
    'G5pe4'
    >>> parse_opdb_group_id(None)
    ''
    """
    if not opdb_id:
        return ""
    return opdb_id.split("-")[0]
