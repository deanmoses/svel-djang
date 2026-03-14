"""Markdown rendering pipeline.

Shared utility for converting markdown text to sanitized HTML. Used by
API serializers to produce ``{field}_html`` output for markdown fields.
"""

import re

import nh3
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

# CommonMark-compliant markdown parser.
# - linkify: auto-link bare URLs during parsing (structure-aware, won't
#   linkify inside code blocks or existing links)
# - breaks: single newlines become <br> (equiv. to Python-Markdown's nl2br)
# - typographer + smartquotes/replacements: smart quotes, em dashes, ellipsis
#   (equiv. to Python-Markdown's smarty)
# - fenced code blocks are built into the commonmark preset
_md = MarkdownIt(
    "commonmark", {"linkify": True, "breaks": True, "typographer": True}
).enable(["linkify", "replacements", "smartquotes", "table", "strikethrough"])

# Allowed HTML tags for markdown rendering
ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "s",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "blockquote",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "img",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "figure",
    "figcaption",
}

# Allowed attributes per tag
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
    "pre": {"class"},
    "th": {"align"},
    "td": {"align"},
}

# Regex for task list items: matches <li> followed by optional <p>, then [ ], [  ], [], [x], or [X]
# Group 1: optional whitespace+<p> (for blank-line-separated list items)
# Group 2: the check character to determine checked state (spaces or empty = unchecked)
_TASK_LIST_RE = re.compile(r"<li>(\s*<p>)?\s*\[( *|[xX])\]")


def _convert_task_list_items(html: str) -> str:
    """Convert task list markers in <li> tags to checkbox HTML.

    After markdown and nh3 processing, literal [ ] and [x] text inside <li> tags
    is converted to checkbox inputs. Each checkbox gets a sequential
    data-checkbox-index attribute for JavaScript targeting.

    This runs AFTER nh3 sanitization, so the injected <input> elements are
    trusted server code, not user-supplied HTML.

    Args:
        html: Sanitized HTML containing <li>[ ] or <li>[x] patterns

    Returns:
        HTML with task list markers replaced by checkbox inputs
    """
    counter = 0

    def _replace(match: re.Match) -> str:
        nonlocal counter
        idx = counter
        counter += 1
        p_tag = (
            match.group(1) or ""
        )  # Preserve <p> if present (blank-line-separated items)
        check_char = match.group(2)
        checked_attr = " checked" if check_char in ("x", "X") else ""
        return (
            f'<li class="task-list-item">{p_tag}'
            f'<input type="checkbox"{checked_attr} data-checkbox-index="{idx}" disabled>'
        )

    return _TASK_LIST_RE.sub(_replace, html)


def fenced_code_ranges(content: str) -> list[tuple[int, int]]:
    """Return (start, end) character-position ranges of fenced code blocks.

    Uses the MarkdownIt parser to identify code fences, ensuring consistency
    with how the content will actually be rendered.
    """
    tokens = _md.parse(content)
    line_ranges = [t.map for t in tokens if t.type == "fence" and t.map]
    if not line_ranges:
        return []

    # Build line-number -> character-offset mapping
    offsets = [0]
    for i, ch in enumerate(content):
        if ch == "\n":
            offsets.append(i + 1)

    return [
        (offsets[start], offsets[end] if end < len(offsets) else len(content))
        for start, end in line_ranges
    ]


def render_markdown_html(text: str) -> str:
    """Convert markdown text to sanitized HTML.

    Full pipeline: wiki links -> markdown (with linkify) -> nh3 -> checkboxes.

    Args:
        text: Raw markdown text (may contain ``[[type:ref]]`` links).

    Returns:
        Sanitized HTML ``SafeString``, safe for direct use in templates.
    """
    if not text:
        return ""
    # Convert [[type:ref]] links to markdown links (before markdown processing)
    from apps.core.markdown_links import render_all_links

    text = render_all_links(text)
    # Convert markdown to HTML (bare URLs are auto-linked during parsing)
    html = _md.render(text)
    # Sanitize to prevent XSS
    safe_html = nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
    # Convert task list markers to checkboxes (after sanitization for security)
    return mark_safe(_convert_task_list_items(safe_html))  # noqa: S308 — HTML sanitized by nh3


def render_markdown_fields(obj) -> dict[str, str]:
    """Return ``{field}_html`` rendered values for all MarkdownField instances on *obj*.

    Designed for use with ``**`` spread in API serialization dicts::

        return {
            "name": obj.name,
            "description": obj.description,
            **render_markdown_fields(obj),
        }
    """
    from apps.core.models import get_markdown_fields

    return {
        f"{field}_html": render_markdown_html(getattr(obj, field, ""))
        for field in get_markdown_fields(type(obj))
    }
