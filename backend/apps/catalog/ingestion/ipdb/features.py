"""IPDB feature, theme, and reward-type extraction.

Pure parsing functions — no database writes.  Extracted from the
``ingest_ipdb`` management command so they can be shared between
the adapter (plan/apply) and tests.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Theme parsing
# ---------------------------------------------------------------------------

# Raw IPDB tag → list of canonical theme slugs.
# After splitting on " - ", each token is looked up here.
# Unmapped tags are logged as warnings.
IPDB_TAG_MAP: dict[str, list[str]] = {
    # Spelling/encoding fixes
    "Basebal": ["baseball"],
    "BIlliards": ["billiards"],
    "Music \ufffd Singing": ["music"],
    # Duplicate normalization
    "Circus/Carnival": ["circus"],
    "Circus / Carnival": ["circus"],
    "Auto racing": ["auto-racing"],
}


def parse_ipdb_themes(raw_theme: str) -> list[str]:
    """Split an IPDB theme string and return canonical theme slugs.

    Splits on `` - `` (and ``, `` for comma-delimited entries), looks up
    each token in IPDB_TAG_MAP (or slugifies if unmapped), and returns
    deduplicated slugs.
    """
    from django.utils.text import slugify

    tags: list[str] = []
    for part in raw_theme.split(" - "):
        for sub in part.split(", "):
            tag = sub.strip()
            if tag:
                tags.append(tag)

    slugs: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        mapped = IPDB_TAG_MAP.get(tag)
        if mapped:
            for slug in mapped:
                if slug not in seen:
                    slugs.append(slug)
                    seen.add(slug)
        else:
            slug = slugify(tag)
            if slug and slug not in seen:
                slugs.append(slug)
                seen.add(slug)
    return slugs


# ---------------------------------------------------------------------------
# Gameplay feature extraction
# ---------------------------------------------------------------------------

# Regex patterns for features that appear in narrative text rather than
# the structured "Feature (N)" list.  Each pattern is matched against
# the full notable_features string.  Target slugs are validated at startup
# against the DB-driven feature/reward-type maps.
_NARRATIVE_FEATURE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[Mm]ulti-?ball\b"), "multiball"),
    (re.compile(r"\b[Kk]ickback\b"), "kickback"),
    (re.compile(r"\b[Mm]agna.?[Ss]ave\b"), "magna-save"),
    (re.compile(r"\b[Bb]all [Ss]ave\b"), "ball-save"),
    (re.compile(r"\b[Ss]kill.?[Ss]hot\b"), "skill-shot"),
    (
        re.compile(
            r"\b[Mm]ulti.?level playfield\b"
            r"|\b[Uu]pper playfield\b"
            r"|\b[Ee]levated.{0,20}playfield\b"
            r"|\b[Mm]ini.?playfield\b"
        ),
        "multi-level-playfield",
    ),
    (re.compile(r"\b[Hh]ead.?to.?[Hh]ead\b"), "head-to-head"),
]

# Regex for inserting a comma before a period followed by an uppercase letter.
# Handles IPDB encoding artifacts like "5 cents.Flippers" → "5 cents,Flippers".
_PERIOD_UPPERCASE_RE = re.compile(r"\.(?=[A-Z])")

# Regex for extracting "feature name (count)" from a segment.
# Requires a bare integer in parens — \(\d+\) — matching only "Flippers (2)",
# not narrative like "(42 inches long...)" or "(5-ball mode)".
# Group 1 = feature name, group 2 = count.
# No $ anchor so trailing description text is ignored.
_COUNT_SEGMENT_RE = re.compile(r"^(.+?)\s*\((\d+)\)")

# ---------------------------------------------------------------------------
# Multiball special handling
#
# For every other IPDB feature the parenthesized number is a *quantity*
# ("Flippers (2)" = two flippers).  For multiball the number is a
# *qualifier* that identifies WHICH feature: "Multiball (3)" means
# 3-ball-multiball, NOT "three instances of multiball."
#
# When future quantity capture is added, multiball must NOT store the
# parenthesized number as a quantity — it is consumed into the slug here.
# ---------------------------------------------------------------------------
_MULTIBALL_SLUG = "multiball"

# Matches "Multiball (...)" with any paren content (not just bare integers).
# Used as a fallback when _COUNT_SEGMENT_RE doesn't match.
_MULTIBALL_PAREN_RE = re.compile(r"^[Mm]ulti-?ball\s*\((.+)\)")

# Inside multiball parens, extracts digits that are ball counts.
# Negative lookahead excludes digits followed by "mode" (e.g. "3 modes").
_MULTIBALL_BALL_COUNT_RE = re.compile(r"(\d+)(?![\s-]*[Mm]ode)")

# Narrative: "3-ball multiball", "2-ball and 3-ball Multiball", etc.
# Captures the compound prefix so all N values can be extracted.
_NBALL_MULTIBALL_RE = re.compile(
    r"\b((?:\d+-ball\s+(?:and|or)\s+)*\d+-ball)\s+[Mm]ulti-?ball\b"
)

# Spelled-out numbers for "Three ball multiball" etc.
_WORD_TO_DIGIT: dict[str, str] = {
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
}
_WORD_NBALL_MULTIBALL_RE = re.compile(
    r"\b(two|three|four|five|six)[\s-]*ball\s+[Mm]ulti-?ball\b", re.IGNORECASE
)


def _resolve_multiball_slugs(paren_content: str, valid_slugs: set[str]) -> list[str]:
    """Extract n-ball-multiball slugs from multiball paren content.

    Handles: "3", "2-ball", "3 ball", "3 balls", "2 or 3",
    "2 ball, 3 ball", "2-Ball, 3-Ball, 4-Ball", "4 ball, 3 modes".
    Skips digits followed by "mode/modes" (not ball counts).
    Falls back to generic "multiball" if no valid n-ball slugs found.
    """
    results: list[str] = []
    for m in _MULTIBALL_BALL_COUNT_RE.finditer(paren_content):
        specific = f"{m.group(1)}-ball-multiball"
        if specific in valid_slugs:
            results.append(specific)
    return results if results else [_MULTIBALL_SLUG]


def extract_ipdb_gameplay_features(
    raw: str, feature_map: dict[str, str]
) -> tuple[list[tuple[str, int | None]], list[str]]:
    """Extract gameplay feature slugs and counts from an IPDB notable_features string.

    Uses a structured 4-step pipeline:
    1. Clean: strip prefix, normalize mojibake, insert comma before period+uppercase.
    2. Split: on comma or period+whitespace; strip preamble before colon.
    3. Parse: process segments with "Feature (N)" count syntax, plus
       "Multiball (...)" segments with complex paren content.
    4. Classify: look up extracted feature name in feature_map.
       Also apply _NARRATIVE_FEATURE_PATTERNS and n-ball-multiball
       narrative patterns to the full cleaned text.

    Returns ``([(slug, count | None), ...], unmatched_terms)``.

    For multiball the parenthesized number is consumed into the slug
    (e.g. "Multiball (3)" → "3-ball-multiball") and is NOT stored as a
    count.  Narrative-pattern matches have ``count=None``.
    """
    seen: set[str] = set()
    pairs: list[tuple[str, int | None]] = []
    unmatched: list[str] = []
    valid_slugs = set(feature_map.values())

    def _add(slug: str, count: int | None = None) -> None:
        if slug not in seen:
            seen.add(slug)
            pairs.append((slug, count))

    # Step 1: Clean.
    cleaned = raw
    if cleaned.lower().startswith("notable features:"):
        cleaned = cleaned[len("notable features:") :]
    cleaned = cleaned.replace("\ufffd", " ")
    cleaned = _PERIOD_UPPERCASE_RE.sub(",", cleaned)

    # Step 2: Split on comma or period+whitespace.
    # The comma split uses a negative lookahead to avoid splitting inside
    # parentheses, e.g. "Multiball (2-Ball, 3-Ball, 4-Ball)" stays intact.
    segments: list[str] = []
    for part in re.split(r",(?![^()]*\))|\.(?:\s+)", cleaned):
        segment = part.strip()
        if not segment:
            continue
        # Strip preamble text before a colon within each segment.
        if ":" in segment:
            segment = segment.split(":", 1)[1].strip()
        if segment:
            segments.append(segment)

    # Step 3 + 4: Parse then classify.
    for segment in segments:
        # Branch 1: standard "Feature (N)" count syntax.
        m = _COUNT_SEGMENT_RE.match(segment)
        if m:
            term = m.group(1).strip().lower()
            qty = int(m.group(2))
            if not term:
                continue
            slug = feature_map.get(term)
            if slug:
                # Multiball special case: the parenthesized number is NOT a
                # quantity — it identifies WHICH multiball variant.
                # "Multiball (3)" → 3-ball-multiball, not multiball qty=3.
                if slug == _MULTIBALL_SLUG:
                    for s in _resolve_multiball_slugs(str(qty), valid_slugs):
                        _add(s)
                else:
                    _add(slug, qty)
            else:
                unmatched.append(term)
            continue

        # Branch 2: "Multiball (...)" with complex paren content that doesn't
        # match bare-integer syntax, e.g. "Multiball (2-ball)",
        # "Multiball (4 ball, 3 modes)".
        mb_m = _MULTIBALL_PAREN_RE.match(segment)
        if mb_m:
            for s in _resolve_multiball_slugs(mb_m.group(1), valid_slugs):
                _add(s)

    # Narrative patterns applied to cleaned text.
    for pattern, slug in _NARRATIVE_FEATURE_PATTERNS:
        if pattern.search(cleaned):
            _add(slug)

    # N-ball multiball narrative: "3-ball Multiball", "2-ball and 3-ball Multiball"
    for nball_m in _NBALL_MULTIBALL_RE.finditer(cleaned):
        # Extract all digit values from the compound prefix
        # e.g. "2-ball and 3-ball" → ["2", "3"]
        for digit in re.findall(r"(\d+)-ball", nball_m.group(1)):
            specific = f"{digit}-ball-multiball"
            if specific in valid_slugs:
                _add(specific)

    # Spelled-out: "Three ball multiball"
    wm = _WORD_NBALL_MULTIBALL_RE.search(cleaned)
    if wm:
        digit = _WORD_TO_DIGIT.get(wm.group(1).lower())
        if digit:
            specific = f"{digit}-ball-multiball"
            if specific in valid_slugs:
                _add(specific)

    # If a specific n-ball-multiball variant was found, suppress the generic
    # "multiball" slug — the hierarchy already links variants to the parent.
    if any(s.endswith("-ball-multiball") for s in seen) and _MULTIBALL_SLUG in seen:
        pairs = [(s, c) for s, c in pairs if s != _MULTIBALL_SLUG]
        seen.discard(_MULTIBALL_SLUG)

    return pairs, unmatched


# ---------------------------------------------------------------------------
# Reward type extraction
# ---------------------------------------------------------------------------


def extract_ipdb_reward_types(raw: str, reward_map: dict[str, str]) -> list[str]:
    """Extract reward type slugs from an IPDB notable_features string.

    Uses word-boundary keyword matching against the raw text — reward types
    appear as keywords in IPDB narrative text with or without counts.

    Returns deduplicated slugs in discovery order.
    """
    seen: set[str] = set()
    slugs: list[str] = []
    for term, slug in reward_map.items():
        if (
            re.search(r"\b" + re.escape(term) + r"\b", raw, re.IGNORECASE)
            and slug not in seen
        ):
            seen.add(slug)
            slugs.append(slug)
    return slugs


# ---------------------------------------------------------------------------
# MPU / system lookup
# ---------------------------------------------------------------------------


def load_mpu_to_system_slug() -> dict[str, str]:
    """Build {mpu_string: system_slug} from SystemMpuString records."""
    from apps.catalog.models import SystemMpuString

    return {
        ms.value: ms.system.slug
        for ms in SystemMpuString.objects.select_related("system").all()
    }


# ---------------------------------------------------------------------------
# Vocabulary validation
# ---------------------------------------------------------------------------


def validate_narrative_slugs(all_vocab_slugs: set[str]) -> list[str]:
    """Return narrative pattern slugs not found in the vocabulary.

    Raises nothing — caller decides whether to error.
    """
    return [
        slug for _, slug in _NARRATIVE_FEATURE_PATTERNS if slug not in all_vocab_slugs
    ]
