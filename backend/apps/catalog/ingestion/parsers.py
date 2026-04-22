"""Parsing utilities for IPDB and OPDB data ingestion."""

from __future__ import annotations

import re
from typing import Any


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
    month: int | None = int(match.group(2))
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

# Normalization maps ported from pinexplore/sql/01_reference.sql.
_COUNTRY_NORMALIZATION: dict[str, str] = {
    "England": "United Kingdom",
    "Scotland": "United Kingdom",
    "Wales": "United Kingdom",
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
# Values are canonical location_path strings from Location records.
_IPDB_LOCATION_OVERRIDES: dict[int, str] = {
    # "Chicago Illinois" — missing comma between city and state.
    532: "usa/il/chicago",
    # "Long Island City, Queens, New York" — Queens is not a state.
    607: "usa/ny/long-island-city",
    # Malformed Nebraska string.
    764: "usa/ne/lincoln",
    # Malformed Ohio string.
    696: "usa/oh/youngstown",
    # "Madrid" alone — ambiguous between Madrid province and city; use city.
    439: "spain/mad/madrid/madrid",
    # Malformed France string — Marcoussis is in Essonne, Île-de-France.
    364: "france/idf/essonne/marcoussis",
    # Malformed Italy string — Avenza is in Massa-Carrara province.
    135: "italy/ms/avenza",
    # IPDB spells "Pittsburgh, Kansas" with an h — correct spelling is Pittsburg (no h).
    290: "usa/ks/pittsburg",
    # IPDB incorrectly lists Tecnoplay under Italy — it is in the country of San Marino.
    313: "san-marino/san-marino",
    # IPDB drops the h from Pittsburgh, PA — correct spelling has an h.
    433: "usa/pa/pittsburgh",
    # IPDB says "Brabant, Belgium" — Brabant is a historical region; correct location is Aartselaar.
    590: "belgium/aartselaar",
    # IPDB says "Taiwan, R.O.C." — country is named "Taiwan" in pindata.
    761: "taiwan/kaohsiung",
    # IPDB includes "Hertfordshire" county which isn't in pindata; Hoddesdon is a direct child of uk/eng.
    770: "uk/eng/hoddesdon",
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


def _get_location_root(loc: Any) -> Any:
    """Walk the parent chain to find the root (country) Location."""
    while loc.parent is not None:
        loc = loc.parent
    return loc


class _IPDBLocationLookup:
    """Resolves parsed IPDB {city, state, country} dicts to canonical location_path strings.

    Builds lookup tables from Location + LocationAlias records at construction time.
    Handles arbitrary hierarchy depths: US 3-level (country→state→city) and
    European 4-level (country→region→province→city) via a country-wide fallback map.
    """

    def __init__(self) -> None:
        from apps.catalog.models import Location, LocationAlias

        # (parent_path_or_None, lower_name) → location_path (direct parent relationships)
        self._by_parent: dict[tuple[str | None, str], str] = {}
        # country_path → {lower_name → location_path} (any descendant within country)
        self._by_country: dict[str, dict[str, str]] = {}

        locs = list(
            Location.objects.select_related("parent__parent__parent__parent").all()
        )
        for loc in locs:
            parent_path = loc.parent.location_path if loc.parent else None
            self._by_parent.setdefault(
                (parent_path, loc.name.lower()), loc.location_path
            )

            root = _get_location_root(loc)
            if root.location_path != loc.location_path:
                country_map = self._by_country.setdefault(root.location_path, {})
                country_map.setdefault(loc.name.lower(), loc.location_path)

        aliases = LocationAlias.objects.select_related(
            "location__parent__parent__parent__parent"
        ).all()
        for alias in aliases:
            loc = alias.location
            parent_path = loc.parent.location_path if loc.parent else None
            val = alias.value.lower()
            self._by_parent.setdefault((parent_path, val), loc.location_path)

            root = _get_location_root(loc)
            if root.location_path != loc.location_path:
                country_map = self._by_country.setdefault(root.location_path, {})
                country_map.setdefault(val, loc.location_path)

    def resolve(self, parsed: dict[str, str]) -> str | None:
        """Resolve a parsed {city, state, country} dict to a location_path, or None."""
        country_name = parsed.get("country", "").strip()
        state_name = parsed.get("state", "").strip()
        city_name = parsed.get("city", "").strip()

        if not country_name:
            return None

        country_path = self._by_parent.get((None, country_name.lower()))
        if not country_path:
            return None

        if not state_name and not city_name:
            return country_path

        if state_name:
            subdiv_path = self._by_parent.get((country_path, state_name.lower()))
            if not subdiv_path:
                # For 4-level hierarchies (Spain, France) the subdivision is not a
                # direct child of the country — search all country descendants.
                subdiv_path = self._by_country.get(country_path, {}).get(
                    state_name.lower()
                )
            if not subdiv_path:
                return None
            if not city_name:
                return subdiv_path
            return self._by_parent.get((subdiv_path, city_name.lower()))

        # City with no state — try direct child of country first (e.g. Netherlands→Reuver),
        # then fall back to any descendant within the country (handles 4-level hierarchies).
        path = self._by_parent.get((country_path, city_name.lower()))
        if path:
            return path
        return self._by_country.get(country_path, {}).get(city_name.lower())


def get_ipdb_location(
    mfr_id: int, location: str, lookup: _IPDBLocationLookup
) -> str | None:
    """Resolve an IPDB manufacturer's location string to a canonical location_path.

    Checks per-manufacturer overrides first (for malformed IPDB strings), then
    parses the location string and resolves it via the DB-backed lookup.

    Returns the location_path string, or None if the location string is empty
    or cannot be resolved.
    """
    override = _IPDB_LOCATION_OVERRIDES.get(mfr_id)
    if override is not None:
        return override
    parsed = parse_ipdb_location(location)
    if not any(parsed.values()):
        return None
    return lookup.resolve(parsed)


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
