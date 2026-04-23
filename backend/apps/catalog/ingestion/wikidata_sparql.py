"""Wikidata SPARQL fetch and parse utilities for pinball data.

No Django dependency — pure Python. Testable in isolation.

Person pipeline
---------------
The Wikidata SPARQL endpoint kills queries that exceed ~60 seconds.
Fetching all (person, machine) pairs with biographical OPTIONAL clauses
and label lookups in a single query is too slow.

Instead we run three targeted queries:

1. **Persons query** — returns only DISTINCT person QIDs + English names for
   humans credited on pinball machines.  No works, no biographical data.
   Tiny result set → label service is fast → runs in a few seconds.

2. **Bio query** — uses a ``VALUES`` clause limited to the QIDs found in
   step 1, so biographical data is fetched for only a known small set.
   Also runs in a few seconds.

3. **Credits queries** — one simple query per Wikidata property (P287, P943,
   P725, P86).  UNION across properties times out on the endpoint; four
   targeted queries of ~10–44 rows each run in ~1s apiece.

Dump format written by ``fetch_sparql()`` (and read by ``--from-dump``):
``{"persons": <sparql-result>, "bio": <sparql-result>, "credits": <sparql-result>}``.

Manufacturer pipeline
---------------------
Two targeted queries:

1. **Manufacturers query** — DISTINCT manufacturer QIDs + labels from P176
   (manufacturer) on pinball machines.  Small result set, fast.

2. **Manufacturer bio query** — uses a ``VALUES`` clause for the known QIDs;
   fetches inception date, dissolution date, country, headquarters, logo, website.

Dump format written by ``fetch_manufacturer_sparql()`` (and read by ``--from-dump``):
``{"manufacturers": <sparql-result>, "bio": <sparql-result>}``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

import requests

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "Pinbase/1.0 (Project of The Flip pinball museum; contact via github.com/deanmoses/pinbase)"

# Wikidata property → Credit.role mapping.
# Only properties that link humans to pinball machines and have meaningful
# coverage in Wikidata are included here.
PROP_TO_ROLE: dict[str, str] = {
    "P287": "design",  # designed by
    "P943": "software",  # programmer
    "P725": "voice",  # voice actor
    "P86": "music",  # composer
}

# Wikidata date precision constants (wikibase:timePrecision)
PRECISION_DAY = 11
PRECISION_MONTH = 10
PRECISION_YEAR = 9
# Anything below PRECISION_YEAR (decade=8, century=7, ...) is too coarse to use.

# Query 1: DISTINCT humans credited on pinball machines, names only.
# No works, no biographical data — keeps the result set tiny so the
# label service is fast.  Runs in a few seconds.
#
# Q653928 = "pinball machine game" (the correct Wikidata class).
# P287  = designed by       (game design)
# P943  = programmer        (software/code)
# P725  = voice actor       (voice samples)
# P86   = composer          (music)
_SPARQL_PERSONS_QUERY = """
SELECT DISTINCT ?person ?personLabel
WHERE {
  ?work wdt:P31 wd:Q653928 .
  ?work wdt:P287|wdt:P943|wdt:P725|wdt:P86 ?person .
  ?person wdt:P31 wd:Q5 .
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""

# Query 2 template: biographical data for a known set of person QIDs.
# VALUES bounds the engine to only the persons we care about.
_SPARQL_BIO_QUERY_TEMPLATE = """
SELECT DISTINCT
  ?person ?personDescription
  ?birthDate ?birthDatePrecision
  ?deathDate ?deathDatePrecision
  ?birthPlaceLabel ?citizenshipLabel
  ?image
WHERE {{
  VALUES ?person {{ {qid_values} }}

  OPTIONAL {{
    ?person wdt:P569 ?birthDate .
    ?person p:P569/psv:P569/wikibase:timePrecision ?birthDatePrecision .
  }}
  OPTIONAL {{
    ?person wdt:P570 ?deathDate .
    ?person p:P570/psv:P570/wikibase:timePrecision ?deathDatePrecision .
  }}
  OPTIONAL {{
    ?person wdt:P19 ?birthPlace .
    ?birthPlace rdfs:label ?birthPlaceLabel .
    FILTER(LANG(?birthPlaceLabel) = "en")
  }}
  OPTIONAL {{
    ?person wdt:P27 ?citizenship .
    ?citizenship rdfs:label ?citizenshipLabel .
    FILTER(LANG(?citizenshipLabel) = "en")
  }}
  OPTIONAL {{ ?person wdt:P18 ?image . }}

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
  }}
}}
"""


# Query 3 template: one (machine, person) query per Wikidata property.
# UNION across multiple properties times out on the Wikidata endpoint; running
# one simple query per property is fast (~1s each) and reliable.
_SPARQL_CREDITS_QUERY_TEMPLATE = """
SELECT ?work ?workLabel ?person
WHERE {{
  ?work wdt:P31 wd:Q653928 .
  ?work wdt:{prop} ?person .
  ?person wdt:P31 wd:Q5 .
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
  }}
}}
"""


# Manufacturer query 1: DISTINCT manufacturers (P176) on pinball machines.
_SPARQL_MANUFACTURERS_QUERY = """
SELECT DISTINCT ?manufacturer ?manufacturerLabel
WHERE {
  ?machine wdt:P31 wd:Q653928 .
  ?machine wdt:P176 ?manufacturer .
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""

# Manufacturer query 2 template: structured bio for a known set of QIDs.
# P571 = inception (founded), P576 = dissolved, P17 = country,
# P159 = headquarters location, P154 = logo image, P856 = official website.
_SPARQL_MFR_BIO_QUERY_TEMPLATE = """
SELECT DISTINCT
  ?manufacturer ?manufacturerDescription
  ?inception ?dissolution
  ?countryLabel ?hqLabel
  ?logo ?website
WHERE {{
  VALUES ?manufacturer {{ {qid_values} }}
  OPTIONAL {{ ?manufacturer wdt:P571 ?inception . }}
  OPTIONAL {{ ?manufacturer wdt:P576 ?dissolution . }}
  OPTIONAL {{
    ?manufacturer wdt:P17 ?country .
    ?country rdfs:label ?countryLabel .
    FILTER(LANG(?countryLabel) = "en")
  }}
  OPTIONAL {{
    ?manufacturer wdt:P159 ?hq .
    ?hq rdfs:label ?hqLabel .
    FILTER(LANG(?hqLabel) = "en")
  }}
  OPTIONAL {{ ?manufacturer wdt:P154 ?logo . }}
  OPTIONAL {{ ?manufacturer wdt:P856 ?website . }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
  }}
}}
"""


@dataclass
class WikidataCredit:
    work_qid: str  # e.g. "Q2789375"
    work_label: str  # e.g. "The Addams Family"
    role: str  # "design" | "software" | "voice" | "music"


@dataclass
class WikidataPerson:
    qid: str  # e.g. "Q312897"
    name: str
    description: str  # Short Wikidata description (1-2 sentences), may be ""
    birth_date: str | None  # Raw "+1951-10-15T00:00:00Z" or None
    birth_precision: int | None  # 9/10/11 or None
    death_date: str | None
    death_precision: int | None
    birth_place: str | None  # English label, e.g. "Chicago"
    nationality: str | None  # English label, e.g. "United States of America"
    photo_url: str | None  # https://commons.wikimedia.org/wiki/Special:FilePath/...
    credits: list[WikidataCredit] = field(default_factory=list)
    citation_url: str = ""  # https://www.wikidata.org/wiki/{qid}


@dataclass
class WikidataManufacturer:
    qid: str  # e.g. "Q180268"
    name: str  # Wikidata label, e.g. "Williams Electronics"
    description: str  # Short Wikidata description, may be ""
    year_start: int | None
    year_end: int | None
    country: str | None  # English label, e.g. "United States of America"
    headquarters: str | None  # English label, e.g. "Chicago"
    logo_url: str | None
    website: str  # may be ""
    citation_url: str  # https://www.wikidata.org/wiki/{qid}


def fetch_sparql(timeout: int = 5) -> dict:
    """Run all queries and return a combined result dict.

    The returned dict has the shape ``{"persons": <sparql-result>, "bio":
    <sparql-result>, "credits": <sparql-result>}`` — suitable for passing
    to ``parse_sparql_results()`` or saving as a ``--dump`` file.

    Raises ``requests.RequestException`` on network failure.
    Raises ``ValueError`` if a response is missing expected keys.
    """
    # Step 1: find all distinct humans credited on pinball machines.
    persons_data = _run_sparql(_SPARQL_PERSONS_QUERY, timeout=timeout)

    # Step 2: collect QIDs and fetch bio data only for those persons.
    qids = _extract_person_qids(persons_data)
    if not qids:
        empty: dict = {"results": {"bindings": []}}
        return {"persons": persons_data, "bio": empty, "credits": empty}

    bio_query = _SPARQL_BIO_QUERY_TEMPLATE.format(
        qid_values=" ".join(f"wd:{qid}" for qid in sorted(qids))
    )
    bio_data = _run_sparql(bio_query, timeout=timeout)

    # Step 3: fetch credit triples — one query per property to avoid UNION
    # timeouts.  Inject a synthetic "prop" field so the caller can map to roles.
    all_credit_bindings: list[dict] = []
    for prop in PROP_TO_ROLE:
        query = _SPARQL_CREDITS_QUERY_TEMPLATE.format(prop=prop)
        result = _run_sparql(query, timeout=timeout)
        for binding in result["results"]["bindings"]:
            binding["prop"] = {"type": "literal", "value": prop}
        all_credit_bindings.extend(result["results"]["bindings"])
    credits_data = {"results": {"bindings": all_credit_bindings}}

    return {"persons": persons_data, "bio": bio_data, "credits": credits_data}


def parse_sparql_results(data: dict) -> list[WikidataPerson]:
    """Parse the combined fetch_sparql() result into a list of WikidataPerson.

    ``data`` must have ``"persons"``, ``"bio"``, and ``"credits"`` keys, each
    containing a standard SPARQL JSON result, as returned by ``fetch_sparql()``
    or loaded from a ``--dump`` file.

    Returns list sorted by name for deterministic output.
    """
    persons: dict[str, WikidataPerson] = {}

    # Pass 1: build persons from the persons query (names + QIDs).
    for binding in data["persons"]["results"]["bindings"]:
        person_uri = binding.get("person", {}).get("value", "")
        if not person_uri:
            continue
        qid = person_uri.rstrip("/").rsplit("/", 1)[-1]

        if qid not in persons:
            persons[qid] = WikidataPerson(
                qid=qid,
                name=binding.get("personLabel", {}).get("value", ""),
                description="",
                birth_date=None,
                birth_precision=None,
                death_date=None,
                death_precision=None,
                birth_place=None,
                nationality=None,
                photo_url=None,
                citation_url=f"https://www.wikidata.org/wiki/{qid}",
            )

    # Pass 2: enrich persons with biographical data from the bio query.
    for binding in data["bio"]["results"]["bindings"]:
        person_uri = binding.get("person", {}).get("value", "")
        if not person_uri:
            continue
        qid = person_uri.rstrip("/").rsplit("/", 1)[-1]

        if (wp := persons.get(qid)) is None:
            continue

        # Only set fields that aren't already populated (first binding wins).
        if not wp.description:
            wp.description = binding.get("personDescription", {}).get("value", "")
        if wp.birth_date is None:
            wp.birth_date = binding.get("birthDate", {}).get("value")
            wp.birth_precision = _int_binding(binding, "birthDatePrecision")
        if wp.death_date is None:
            wp.death_date = binding.get("deathDate", {}).get("value")
            wp.death_precision = _int_binding(binding, "deathDatePrecision")
        if wp.birth_place is None:
            wp.birth_place = binding.get("birthPlaceLabel", {}).get("value") or None
        if wp.nationality is None:
            wp.nationality = binding.get("citizenshipLabel", {}).get("value") or None
        if wp.photo_url is None:
            wp.photo_url = _normalize_photo_url(binding.get("image", {}).get("value"))

    # Pass 3: attach credit triples to persons.
    for binding in data["credits"]["results"]["bindings"]:
        person_uri = binding.get("person", {}).get("value", "")
        work_uri = binding.get("work", {}).get("value", "")
        if not person_uri or not work_uri:
            continue
        person_qid = person_uri.rstrip("/").rsplit("/", 1)[-1]
        work_qid = work_uri.rstrip("/").rsplit("/", 1)[-1]
        work_label = binding.get("workLabel", {}).get("value", "")
        prop = binding.get("prop", {}).get("value", "")
        role = PROP_TO_ROLE.get(prop)
        if role and (wp := persons.get(person_qid)):
            wp.credits.append(
                WikidataCredit(work_qid=work_qid, work_label=work_label, role=role)
            )

    return sorted(persons.values(), key=lambda p: p.name.lower())


def fetch_manufacturer_sparql(timeout: int = 5) -> dict:
    """Run manufacturer queries and return a combined result dict.

    The returned dict has the shape ``{"manufacturers": <sparql-result>,
    "bio": <sparql-result>}`` — suitable for passing to
    ``parse_manufacturer_sparql_results()`` or saving as a ``--dump`` file.

    Raises ``requests.RequestException`` on network failure.
    Raises ``ValueError`` if a response is missing expected keys.
    """
    manufacturers_data = _run_sparql(_SPARQL_MANUFACTURERS_QUERY, timeout=timeout)

    qids = _extract_qids(manufacturers_data, "manufacturer")
    if not qids:
        empty: dict = {"results": {"bindings": []}}
        return {"manufacturers": manufacturers_data, "bio": empty}

    bio_query = _SPARQL_MFR_BIO_QUERY_TEMPLATE.format(
        qid_values=" ".join(f"wd:{qid}" for qid in sorted(qids))
    )
    bio_data = _run_sparql(bio_query, timeout=timeout)

    return {"manufacturers": manufacturers_data, "bio": bio_data}


def parse_manufacturer_sparql_results(data: dict) -> list[WikidataManufacturer]:
    """Parse the combined fetch_manufacturer_sparql() result into a list of WikidataManufacturer.

    ``data`` must have ``"manufacturers"`` and ``"bio"`` keys, each containing
    a standard SPARQL JSON result, as returned by ``fetch_manufacturer_sparql()``
    or loaded from a ``--dump`` file.

    Returns list sorted by name for deterministic output.
    """
    manufacturers: dict[str, WikidataManufacturer] = {}

    # Pass 1: build manufacturer stubs from the manufacturers query.
    for binding in data["manufacturers"]["results"]["bindings"]:
        uri = binding.get("manufacturer", {}).get("value", "")
        if not uri:
            continue
        qid = uri.rstrip("/").rsplit("/", 1)[-1]
        if qid not in manufacturers:
            manufacturers[qid] = WikidataManufacturer(
                qid=qid,
                name=binding.get("manufacturerLabel", {}).get("value", ""),
                description="",
                year_start=None,
                year_end=None,
                country=None,
                headquarters=None,
                logo_url=None,
                website="",
                citation_url=f"https://www.wikidata.org/wiki/{qid}",
            )

    # Pass 2: enrich with biographical data.
    for binding in data["bio"]["results"]["bindings"]:
        uri = binding.get("manufacturer", {}).get("value", "")
        if not uri:
            continue
        qid = uri.rstrip("/").rsplit("/", 1)[-1]
        if (wm := manufacturers.get(qid)) is None:
            continue

        # Only set fields that aren't already populated (first binding wins).
        if not wm.description:
            wm.description = binding.get("manufacturerDescription", {}).get("value", "")
        if wm.year_start is None:
            wm.year_start = parse_wikidata_date(
                binding.get("inception", {}).get("value"), precision=None
            ).year
        if wm.year_end is None:
            wm.year_end = parse_wikidata_date(
                binding.get("dissolution", {}).get("value"), precision=None
            ).year
        if wm.country is None:
            wm.country = binding.get("countryLabel", {}).get("value") or None
        if wm.headquarters is None:
            wm.headquarters = binding.get("hqLabel", {}).get("value") or None
        if wm.logo_url is None:
            wm.logo_url = _normalize_photo_url(binding.get("logo", {}).get("value"))
        if not wm.website:
            wm.website = binding.get("website", {}).get("value", "")

    return sorted(manufacturers.values(), key=lambda m: m.name.lower())


class WikidataDate(NamedTuple):
    """Parsed Wikidata date components (any may be ``None``).

    ``None`` on ``year`` marks the whole date as absent (precision too coarse
    or unparseable); ``None`` on ``month``/``day`` reflects the precision
    level of the source value.
    """

    year: int | None
    month: int | None
    day: int | None


_EMPTY_DATE = WikidataDate(None, None, None)


def parse_wikidata_date(
    date_str: str | None,
    precision: int | None,
) -> WikidataDate:
    """Parse a Wikidata date string into (year, month, day) integer components.

    Returns ``WikidataDate(None, None, None)`` if the date is absent or
    precision is too coarse (decade or broader).

    Precision rules:
    - precision < PRECISION_YEAR (decade+): ``(None, None, None)``
    - precision == PRECISION_YEAR: ``(year, None, None)``
    - precision == PRECISION_MONTH: ``(year, month, None)``
    - precision >= PRECISION_DAY or None: ``(year, month, day)``
    """
    if not date_str:
        return _EMPTY_DATE

    # Wikidata dates look like "+1951-10-15T00:00:00Z" or "-0044-01-01T00:00:00Z".
    raw = date_str.lstrip("+")
    date_part = raw.split("T")[0]  # "1951-10-15" or "-0044-01-01"

    negative = date_part.startswith("-")
    if negative:
        date_part = date_part[1:]

    parts = date_part.split("-")
    if len(parts) < 1:
        return _EMPTY_DATE

    try:
        year = int(parts[0])
        if negative:
            year = -year
        month = int(parts[1]) if len(parts) > 1 else None
        day = int(parts[2]) if len(parts) > 2 else None
    except ValueError, IndexError:
        return _EMPTY_DATE

    if precision is not None and precision < PRECISION_YEAR:
        return _EMPTY_DATE
    if precision == PRECISION_YEAR:
        return WikidataDate(year, None, None)
    if precision == PRECISION_MONTH:
        return WikidataDate(year, month, None)
    return WikidataDate(year, month, day)


def _run_sparql(query: str, timeout: int) -> dict:
    """Execute a single SPARQL query and return the JSON result dict."""
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if "results" not in data or "bindings" not in data["results"]:
        raise ValueError(f"Unexpected SPARQL response shape: {list(data.keys())}")
    return data


def _extract_qids(result_data: dict, var_name: str) -> list[str]:
    """Return distinct QIDs from a SPARQL result binding under *var_name*."""
    seen: set[str] = set()
    for binding in result_data["results"]["bindings"]:
        uri = binding.get(var_name, {}).get("value", "")
        if uri:
            qid = uri.rstrip("/").rsplit("/", 1)[-1]
            seen.add(qid)
    return list(seen)


def _extract_person_qids(persons_data: dict) -> list[str]:
    """Return distinct person QIDs from a persons query result."""
    return _extract_qids(persons_data, "person")


def _int_binding(binding: dict, key: str) -> int | None:
    val = binding.get(key, {}).get("value")
    if val is None:
        return None
    try:
        return int(val)
    except ValueError, TypeError:
        return None


def _normalize_photo_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url
