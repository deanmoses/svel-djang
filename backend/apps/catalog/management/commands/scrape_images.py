"""Scrape images for pinball machines that don't have artwork.

Quick-and-dirty tool for demo purposes — NOT for production use.

Tries four strategies in order:
0. Hand-picked URLs (MANUAL_IMAGES dict, keyed by opdb_id)
1. Copy from a group sibling (same franchise, different edition)
2. Scrape IPDB page (for machines with IPDB IDs)
3. Search Bing Images (fallback for everything else)

Usage:
    python manage.py scrape_images                    # all machines
    python manage.py scrape_images --year-min 2024    # only 2024+
    python manage.py scrape_images --dry-run           # preview without saving
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from html import unescape
from typing import Any
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from apps.catalog.models import MachineModel
from apps.catalog.resolve import resolve_model
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Seconds to wait between network requests (be polite).
REQUEST_DELAY = 1.5

# Hand-picked image URLs for machines that scrapers can't find. Keyed by opdb_id.
MANUAL_IMAGES: dict[str, list[str]] = {
    "GV8wB-Mq12N": [  # Pokémon (Pro)
        "https://content.abt.com/image.php/stern-pinball-machine-POKEMONPRO-art.jpg?image=/images/products/BDP_Images/stern-pinball-machine-POKEMONPRO-art.jpg&canvas=1&width=750&height=550",
    ],
    "GV8wB-MRjKd": [  # Pokémon (Premium/LE)
        "https://image-cdn.hypb.st/https%3A%2F%2Fhypebeast.com%2Fimage%2F2026%2F02%2F16%2Fstern-pinball-pokemon-pinball-machine-debut-collaboration-release-info-001.jpg?w=1440&cbr=1&q=90&fit=max",
    ],
    "GV8wB-MRjKd-AOVy7": [  # Pokémon (Premium)
        "https://image-cdn.hypb.st/https%3A%2F%2Fhypebeast.com%2Fimage%2F2026%2F02%2F16%2Fstern-pinball-pokemon-pinball-machine-debut-collaboration-release-info-001.jpg?w=1440&cbr=1&q=90&fit=max",
    ],
    "GqZVo-Mb5xK": [  # Beetlejuice
        "https://www.pinballnews.com/site/wp-content/uploads/games/beetlejuice/006-beetlejuice.jpg",
    ],
}


def _has_images(extra_data: dict[str, object]) -> bool:
    """Check if extra_data already contains usable image URLs.

    ``extra_data`` is a free-form JSONField payload — the value side is
    deliberately ``object`` and narrowed via ``isinstance`` per access.
    """
    for key in ("image_urls", "ipdb.image_urls"):
        if extra_data.get(key):
            return True
    images = extra_data.get("opdb.images")
    return bool(images and isinstance(images, list))


def _try_group_sibling(pm: MachineModel) -> list[str] | None:
    """Copy image URLs from a sibling in the same title."""
    if not pm.title:
        return None
    for sib in pm.title.machine_models.exclude(pk=pm.pk):
        ed = sib.extra_data or {}

        images = ed.get("images")
        if images and isinstance(images, list):
            urls = []
            for img in images:
                if not isinstance(img, dict):
                    continue
                img_urls = img.get("urls", {})
                url = (
                    img_urls.get("large")
                    or img_urls.get("medium")
                    or img_urls.get("small")
                )
                if url:
                    urls.append(url)
            if urls:
                return urls

        ipdb_urls = ed.get("image_urls")
        if ipdb_urls and isinstance(ipdb_urls, list):
            return list(ipdb_urls)

    return None


def _try_ipdb_scrape(ipdb_id: int) -> list[str] | None:
    """Scrape image URLs from an IPDB machine page."""
    url = f"https://www.ipdb.org/machine.cgi?id={ipdb_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("IPDB request failed for id=%s: %s", ipdb_id, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []

    for img in soup.find_all("img"):
        src = img.get("src")
        if not isinstance(src, str):
            continue
        if f"/images/{ipdb_id}/" in src:
            full_url = urljoin("https://www.ipdb.org/", src)
            urls.append(full_url)

    return urls if urls else None


def _try_bing_images(query: str) -> list[str] | None:
    """Search Bing Images and return the first few result URLs."""
    search_url = f"https://www.bing.com/images/search?q={quote_plus(query)}&first=1"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("Bing search failed for %r: %s", query, e)
        return None

    text = unescape(resp.text)
    urls = re.findall(r'"murl":"(https?://[^"]+)"', text)

    image_exts = (".jpg", ".jpeg", ".png", ".webp")
    good_urls = [u for u in urls if any(u.lower().endswith(ext) for ext in image_exts)]

    if not good_urls:
        good_urls = [u for u in urls if "." in u.split("/")[-1]]

    return good_urls[:3] if good_urls else None


class Command(BaseCommand):
    help = "Scrape images for machines without artwork (demo tool)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--year-min",
            type=int,
            default=None,
            help="Only process machines from this year onward.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview what would be scraped without saving.",
        )

    def handle(
        self,
        *args: object,
        **options: Any,  # noqa: ANN401 - argparse-driven Django command kwargs
    ) -> None:
        year_min = options["year_min"]
        dry_run = options["dry_run"]

        source, _ = Source.objects.update_or_create(
            slug="web-scrape",
            defaults={
                "name": "Web Scrape",
                "source_type": "other",
                "priority": 10,
                "url": "",
                "description": "Temporary web-scraped images for demo purposes.",
            },
        )

        qs = MachineModel.objects.filter(variant_of__isnull=True).order_by(
            "-year", "name"
        )
        if year_min:
            qs = qs.filter(year__gte=year_min)

        machines = [pm for pm in qs if not _has_images(pm.extra_data or {})]

        total = len(machines)
        if total == 0:
            self.stdout.write(self.style.SUCCESS("All machines already have images!"))
            return

        self.stdout.write(f"Found {total} machines without images.\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be saved.\n"))

        found_count = 0
        for i, pm in enumerate(machines, 1):
            strategy, urls = self._find_images(pm)

            if urls:
                found_count += 1
                if not dry_run:
                    Claim.objects.assert_claim(
                        pm,
                        field_name="image_urls",
                        value=urls,
                        source=source,
                    )
                    resolve_model(pm)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [{i}/{total}] \u2713 {pm.name} [{pm.year}] \u2014 {strategy} ({len(urls)} URLs)"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [{i}/{total}] \u2717 {pm.name} [{pm.year}] \u2014 no images found"
                    )
                )

        if not dry_run:
            from apps.catalog.cache import invalidate_all

            invalidate_all()

        action = "would be updated" if dry_run else "updated"
        self.stdout.write(
            self.style.SUCCESS(f"\nDone! {found_count}/{total} machines {action}.")
        )

    def _find_images(self, pm: MachineModel) -> tuple[str | None, list[str] | None]:
        """Try each strategy in order, return (strategy_name, urls) or (None, None)."""

        if pm.opdb_id and pm.opdb_id in MANUAL_IMAGES:
            return "manual", MANUAL_IMAGES[pm.opdb_id]

        urls = _try_group_sibling(pm)
        if urls:
            return "group sibling", urls

        if pm.ipdb_id:
            time.sleep(REQUEST_DELAY)
            urls = _try_ipdb_scrape(pm.ipdb_id)
            if urls:
                return "IPDB", urls

        time.sleep(REQUEST_DELAY)
        year_part = f" {pm.year}" if pm.year else ""
        query = f'"{pm.name}" pinball{year_part}'
        urls = _try_bing_images(query)
        if urls:
            return "Bing Images", urls

        return None, None
