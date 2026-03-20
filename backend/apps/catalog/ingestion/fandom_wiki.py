"""Pinball Fandom wiki fetch and parse utilities.

No Django dependency — pure Python. Testable in isolation.

Fetch strategy
--------------
The Pinball Fandom wiki (https://pinball.fandom.com) exposes a standard
MediaWiki API.  We use the ``generator=categorymembers`` approach to iterate
all pages in a given category in batches of 50, fetching their wikitext
content in the same request.  Pagination is handled automatically via the
MediaWiki ``continue`` token.

Game pages (Category:Machines)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Each game page contains an ``{{Infobox Title}}`` template whose ``designer``
field encodes all credits, e.g.::

    '''Designers''': [[Larry DeMar]], [[Pat Lawlor]]<br>
    '''Artwork''': [[John Youssi]]<br>
    '''Dots/Animation''': [[Scott Slomiany]]<br>
    '''Mechanics''': [[John Krutsch]]<br>
    '''Sounds/Music''': [[Chris Granner]]<br>
    '''Software''': Larry DeMar, [[Mike Boon]]

This provides roles (art, animation, mechanics) that Wikidata does not cover.

Person pages (Category:People)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Person pages are one-sentence stubs.  The page title is the canonical name
used in wikilinks; the first prose sentence is used as the bio.

Manufacturer pages (Category:Manufacturers)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manufacturer pages use a ``{{Company}}`` template with structured fields:
``founded``, ``defunct``, ``headquarters``, ``website``.  Redirect pages
(e.g. "Bally" → "Midway Manufacturing Company") are skipped.

Dump formats
~~~~~~~~~~~~
- Games:         ``{"games": [{"page_id": int, "title": str, "wikitext": str}, ...]}``
- Persons:       ``{"persons": [{"page_id": int, "title": str, "wikitext": str}, ...]}``
- Manufacturers: ``{"manufacturers": [{"page_id": int, "title": str, "wikitext": str}, ...]}``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests

FANDOM_API = "https://pinball.fandom.com/api.php"
FANDOM_WIKI_BASE = "https://pinball.fandom.com/wiki"
USER_AGENT = "Pinbase/1.0 (Project of The Flip pinball museum; contact via github.com/deanmoses/pinbase)"

# Map of bold-label text in the infobox designer field → Credit.role value.
# Keys are lowercase for case-insensitive matching.
_LABEL_TO_ROLE: dict[str, str] = {
    "designers": "design",
    "designer": "design",
    "design": "design",
    "concept, design": "design",
    "artwork": "art",
    "art": "art",
    "artist": "art",
    "dots/animation": "animation",
    "animation": "animation",
    "dots": "animation",
    "mechanics": "mechanics",
    "mechanical": "mechanics",
    "sounds/music": "music",
    "music": "music",
    "sounds": "sound",
    "sound": "sound",
    "software": "software",
    "programmer": "software",
    "code": "software",
    "voice": "voice",
}

# Regex to strip wikilinks: [[display|target]] → display, [[name]] → name.
_WIKILINK_RE = re.compile(r"\[\[([^\]|]*?)(?:\|[^\]]*?)?\]\]")

# Regex to strip external links: [url display text] → url.
_EXTLINK_RE = re.compile(r"\[(\S+)(?:\s[^\]]*)?\]")

# Regex to extract a credit segment: '''Label''': persons
_CREDIT_SEGMENT_RE = re.compile(r"'''([^']+)'''\s*:\s*(.*)", re.DOTALL)

# Regex to find and extract the {{Infobox Title}} template content.
_INFOBOX_START_RE = re.compile(r"\{\{Infobox\s+Title\b", re.IGNORECASE)

# Regex to find the {{Company}} template.
_COMPANY_START_RE = re.compile(r"\{\{Company\b", re.IGNORECASE)

# Regex to find a 4-digit year.
_YEAR_RE = re.compile(r"\d{4}")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FandomCredit:
    person_name: str
    role: str  # Credit.role value


@dataclass
class FandomGame:
    page_id: int
    title: str
    credits: list[FandomCredit] = field(default_factory=list)
    citation_url: str = ""


@dataclass
class FandomPerson:
    page_id: int
    title: str  # canonical page title = name used in [[wikilinks]]
    bio: str  # first prose paragraph, wikitext-stripped
    citation_url: str = ""


@dataclass
class FandomManufacturer:
    page_id: int
    title: str
    year_start: int | None = None
    year_end: int | None = None
    headquarters: str = ""
    website: str = ""
    description: str = ""
    citation_url: str = ""


# ---------------------------------------------------------------------------
# Public fetch functions
# ---------------------------------------------------------------------------


def fetch_game_pages(timeout: int = 10) -> dict:
    """Fetch all game pages from Category:Machines and return a dump dict.

    The returned dict has shape ``{"games": [{"page_id", "title", "wikitext"}, ...]}``
    — suitable for passing to ``parse_game_pages()`` or saving as a ``--dump`` file.

    Raises ``requests.RequestException`` on network failure.
    """
    return {"games": _fetch_category_pages("Machines", timeout)}


def fetch_person_pages(timeout: int = 10) -> dict:
    """Fetch all person pages from Category:People and return a dump dict.

    Shape: ``{"persons": [{"page_id", "title", "wikitext"}, ...]}``.
    """
    return {"persons": _fetch_category_pages("People", timeout)}


def fetch_manufacturer_pages(timeout: int = 10) -> dict:
    """Fetch all manufacturer pages from Category:Manufacturers and return a dump dict.

    Shape: ``{"manufacturers": [{"page_id", "title", "wikitext"}, ...]}``.
    Includes redirect pages; callers should skip them via ``parse_manufacturer_pages()``.
    """
    return {"manufacturers": _fetch_category_pages("Manufacturers", timeout)}


# ---------------------------------------------------------------------------
# Public parse functions
# ---------------------------------------------------------------------------


def parse_game_pages(data: dict) -> list[FandomGame]:
    """Parse the fetch_game_pages() dump into a list of FandomGame.

    ``data`` must have a ``"games"`` key containing a list of dicts with
    ``"page_id"``, ``"title"``, and ``"wikitext"`` keys.

    Returns a list sorted by title for deterministic output.
    Games with no parseable credits are included (empty credits list).
    """
    games: list[FandomGame] = []
    for entry in data.get("games", []):
        page_id = entry.get("page_id", 0)
        title = entry.get("title", "")
        wikitext = entry.get("wikitext", "")
        credits = _parse_infobox_credits(wikitext)
        title_slug = title.replace(" ", "_")
        games.append(
            FandomGame(
                page_id=page_id,
                title=title,
                credits=credits,
                citation_url=f"{FANDOM_WIKI_BASE}/{title_slug}",
            )
        )
    return sorted(games, key=lambda g: g.title.lower())


def parse_person_pages(data: dict) -> list[FandomPerson]:
    """Parse the fetch_person_pages() dump into a list of FandomPerson.

    Redirect pages (wikitext starting with ``#REDIRECT``) are skipped.
    Returns a list sorted by title.
    """
    persons: list[FandomPerson] = []
    for entry in data.get("persons", []):
        page_id = entry.get("page_id", 0)
        title = entry.get("title", "")
        wikitext = entry.get("wikitext", "")
        if wikitext.lstrip().startswith("#REDIRECT"):
            continue
        bio = _extract_prose(wikitext)
        title_slug = title.replace(" ", "_")
        persons.append(
            FandomPerson(
                page_id=page_id,
                title=title,
                bio=bio,
                citation_url=f"{FANDOM_WIKI_BASE}/{title_slug}",
            )
        )
    return sorted(persons, key=lambda p: p.title.lower())


def parse_manufacturer_pages(data: dict) -> list[FandomManufacturer]:
    """Parse the fetch_manufacturer_pages() dump into a list of FandomManufacturer.

    Redirect pages are skipped.  Pages without a ``{{Company}}`` template are
    included with empty structured fields (description only).
    Returns a list sorted by title.
    """
    manufacturers: list[FandomManufacturer] = []
    for entry in data.get("manufacturers", []):
        page_id = entry.get("page_id", 0)
        title = entry.get("title", "")
        wikitext = entry.get("wikitext", "")
        if wikitext.lstrip().startswith("#REDIRECT"):
            continue
        fields = _parse_company_template(wikitext) or {}
        description = _extract_prose(wikitext)
        title_slug = title.replace(" ", "_")
        manufacturers.append(
            FandomManufacturer(
                page_id=page_id,
                title=title,
                year_start=fields.get("year_start"),
                year_end=fields.get("year_end"),
                headquarters=fields.get("headquarters", ""),
                website=fields.get("website", ""),
                description=description,
                citation_url=f"{FANDOM_WIKI_BASE}/{title_slug}",
            )
        )
    return sorted(manufacturers, key=lambda m: m.title.lower())


# ---------------------------------------------------------------------------
# Private helpers — game credit parsing
# ---------------------------------------------------------------------------


def _parse_infobox_credits(wikitext: str) -> list[FandomCredit]:
    """Parse credits from a game page's wikitext.

    Extracts the ``{{Infobox Title}}`` template, finds the ``designer`` field,
    and parses role-labeled segments into FandomCredit objects.

    Returns an empty list if no infobox or designer field is found.
    """
    infobox = _extract_infobox(wikitext)
    if not infobox:
        return []

    designer_value = _extract_field(infobox, "designer")
    if not designer_value:
        return []

    return _parse_designer_field(designer_value)


def _extract_infobox(wikitext: str) -> str:
    """Return the raw content between {{ and the matching }} for Infobox Title."""
    m = _INFOBOX_START_RE.search(wikitext)
    if not m:
        return ""

    start = m.start()
    depth = 0
    i = start
    while i < len(wikitext) - 1:
        if wikitext[i : i + 2] == "{{":
            depth += 1
            i += 2
        elif wikitext[i : i + 2] == "}}":
            depth -= 1
            if depth == 0:
                return wikitext[start : i + 2]
            i += 2
        else:
            i += 1
    return ""


def _extract_field(infobox: str, field_name: str) -> str:
    """Extract the value of a named field from wikitext template content.

    Handles multi-line values by reading until the next ``|`` at depth 0
    or the closing ``}}``.
    """
    pattern = re.compile(r"\|\s*" + re.escape(field_name) + r"\s*=\s*", re.IGNORECASE)
    m = pattern.search(infobox)
    if not m:
        return ""

    start = m.end()
    depth = 0
    i = start
    while i < len(infobox):
        ch = infobox[i]
        if infobox[i : i + 2] in ("{{", "[["):
            depth += 1
            i += 2
        elif infobox[i : i + 2] in ("}}", "]]"):
            depth -= 1
            if depth < 0:
                # Hit closing }} of the template itself.
                return infobox[start:i].strip()
            i += 2
        elif ch == "|" and depth == 0:
            return infobox[start:i].strip()
        else:
            i += 1
    return infobox[start:].strip()


def _parse_designer_field(value: str) -> list[FandomCredit]:
    """Parse the raw ``designer`` field value into FandomCredit objects.

    Splits on ``<br>`` variants, then for each segment matches the pattern
    ``'''Label''': person1, person2, ...`` and maps the label to a role.
    Segments without a recognisable label are skipped.
    """
    # Normalise <br> variants to a single sentinel.
    normalised = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    segments = [s.strip() for s in normalised.split("\n") if s.strip()]

    credits: list[FandomCredit] = []
    for segment in segments:
        m = _CREDIT_SEGMENT_RE.match(segment)
        if not m:
            continue
        label = m.group(1).strip()
        persons_raw = m.group(2).strip()

        role = _LABEL_TO_ROLE.get(label.lower())
        if not role:
            continue

        for name in _split_person_names(persons_raw):
            if name:
                credits.append(FandomCredit(person_name=name, role=role))

    return credits


def _split_person_names(raw: str) -> list[str]:
    """Strip wikilinks and split a comma-separated person list into names."""
    # Strip wikilinks: [[Display|Target]] → Display, [[Name]] → Name.
    stripped = _WIKILINK_RE.sub(lambda m: m.group(1), raw)
    # Strip any remaining wiki markup (bold/italic apostrophes).
    stripped = stripped.replace("'''", "").replace("''", "")
    return [name.strip() for name in stripped.split(",")]


# ---------------------------------------------------------------------------
# Private helpers — person and manufacturer parsing
# ---------------------------------------------------------------------------


def _fetch_category_pages(category: str, timeout: int = 10) -> list[dict]:
    """Fetch all pages in a Fandom wiki category via the MediaWiki API.

    Returns a list of ``{"page_id": int, "title": str, "wikitext": str}`` dicts.
    Pagination is handled automatically via the MediaWiki ``continue`` token.
    """
    params: dict = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": f"Category:{category}",
        "gcmnamespace": "0",
        "gcmlimit": "50",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "*",
        "format": "json",
        "formatversion": "2",
    }

    pages: list[dict] = []

    while True:
        resp = requests.get(
            FANDOM_API,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        query = data.get("query", {})
        for page in query.get("pages", []):
            page_id = page.get("pageid")
            title = page.get("title", "")
            revisions = page.get("revisions", [])
            if not revisions:
                continue
            rev = revisions[0]
            slots = rev.get("slots", {})
            wikitext = slots.get("main", {}).get("content", rev.get("content", ""))
            if wikitext:
                pages.append({"page_id": page_id, "title": title, "wikitext": wikitext})

        if "continue" not in data:
            break
        params.update(data["continue"])

    return pages


def _extract_prose(wikitext: str) -> str:
    """Extract the first non-empty prose line, stripped of wikitext markup.

    Removes ``{{templates}}``, category links, wikilinks, external links, and
    bold/italic apostrophes.  Returns the first non-blank, non-heading line.
    Redirect pages (``#REDIRECT ...``) return an empty string.
    """
    if wikitext.lstrip().startswith("#REDIRECT"):
        return ""
    # Remove Category links before stripping templates.
    text = re.sub(r"\[\[Category:[^\]]*\]\]", "", wikitext, flags=re.IGNORECASE)
    # Remove all {{...}} template blocks.
    text = _strip_templates(text)
    # Strip wikilinks: [[Display|Target]] → Display, [[Name]] → Name.
    text = _WIKILINK_RE.sub(lambda m: m.group(1), text)
    # Strip external links: [url text] → url.
    text = _EXTLINK_RE.sub(lambda m: m.group(1), text)
    # Strip bold/italic apostrophes.
    text = text.replace("'''", "").replace("''", "")
    # Return first non-empty, non-heading line.
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("="):
            return line
    return ""


def _strip_templates(text: str) -> str:
    """Remove all ``{{...}}`` template blocks from text, preserving surrounding content."""
    result: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        if text[i : i + 2] == "{{":
            depth += 1
            i += 2
        elif text[i : i + 2] == "}}":
            if depth > 0:
                depth -= 1
            i += 2
        elif depth == 0:
            result.append(text[i])
            i += 1
        else:
            i += 1
    return "".join(result)


def _parse_company_template(wikitext: str) -> dict | None:
    """Extract fields from the ``{{Company}}`` template in wikitext.

    Returns a dict with keys ``year_start``, ``year_end``,
    ``headquarters``, ``website``.  Returns ``None`` if no Company template
    is found; missing/unparseable values are ``None`` or ``""``.
    """
    m = _COMPANY_START_RE.search(wikitext)
    if not m:
        return None

    # Extract the full template block using depth counting.
    start = m.start()
    depth = 0
    i = start
    block = ""
    while i < len(wikitext) - 1:
        if wikitext[i : i + 2] == "{{":
            depth += 1
            i += 2
        elif wikitext[i : i + 2] == "}}":
            depth -= 1
            if depth == 0:
                block = wikitext[start : i + 2]
                break
            i += 2
        else:
            i += 1

    if not block:
        return {}

    def _int_year(raw: str) -> int | None:
        ym = _YEAR_RE.search(raw)
        return int(ym.group()) if ym else None

    # Extract website URL from [url display text] markup.
    website_raw = _extract_field(block, "website").strip()
    website_match = _EXTLINK_RE.match(website_raw)
    website = website_match.group(1) if website_match else website_raw

    founded_raw = _extract_field(block, "founded")
    defunct_raw = _extract_field(block, "defunct")

    return {
        "year_start": _int_year(founded_raw) if founded_raw else None,
        "year_end": _int_year(defunct_raw) if defunct_raw else None,
        "headquarters": _extract_field(block, "headquarters").strip(),
        "website": website,
    }
