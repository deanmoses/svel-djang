"""Download ingest source files from Cloudflare R2.

Uses only stdlib (urllib.request) so it works on Railway's slim Python image.

The R2 bucket has two manifests:
  - manifest.json          — root-level ingest sources (IPDB, OPDB, etc.),
                             published by pinexplore.
  - pinbase/manifest.json  — catalog export files, published by pindata.

This command fetches both and downloads the files the ingest pipeline needs.

Usage (local):
    uv run python manage.py pull_ingest_sources --dest ../data/ingest_sources

Usage (Railway):
    .venv/bin/python manage.py pull_ingest_sources --dest /tmp/ingest_sources
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import tempfile
import urllib.request
from typing import Any, cast
from urllib.error import HTTPError

from django.core.management.base import BaseCommand

_OPENER = urllib.request.build_opener()
_OPENER.addheaders = [("User-Agent", "pinbase/1.0")]

_DEFAULT_DEST = os.path.join(tempfile.gettempdir(), "ingest_sources")

# Only download these root-level files from the ingest-sources manifest.
_NEEDED_FILES = {
    "ipdb_xantari.json",
    "opdb_export_machines.json",
    "opdb_changelog.json",
}

# Manifests to fetch: (url_path, local_prefix)
# - Root manifest entries are stored as-is under dest.
# - pinbase/ manifest entries are stored under pinbase/ locally.
_MANIFESTS = [
    ("manifest.json", ""),
    ("pinbase/manifest.json", "pinbase/"),
]


def _urlopen(url: str) -> http.client.HTTPResponse:
    # OpenerDirector.open() is typed as Any in typeshed; the concrete return for
    # http/https URLs is an HTTPResponse.
    return cast(http.client.HTTPResponse, _OPENER.open(url))


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


class Command(BaseCommand):
    help = "Download ingest source files from Cloudflare R2."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--url",
            default=os.environ.get(
                "R2_PUBLIC_URL", "https://pub-8f33ea1ac628450298edd0d3243ecf5a.r2.dev"
            ),
            help="Base URL of the R2 public bucket (default: R2_PUBLIC_URL env var).",
        )
        parser.add_argument(
            "--dest",
            default=_DEFAULT_DEST,
            help=f"Local directory to download into (default: {_DEFAULT_DEST}).",
        )

    def handle(
        self,
        **options: Any,  # noqa: ANN401 - argparse-driven Django command kwargs
    ) -> None:
        base_url = options["url"].rstrip("/")
        dest = options["dest"]

        downloaded = 0
        up_to_date = 0
        ignored = 0

        for manifest_path, local_prefix in _MANIFESTS:
            manifest_url = f"{base_url}/{manifest_path}"
            self.stdout.write(f"Fetching {manifest_url}")
            try:
                with _urlopen(manifest_url) as resp:
                    manifest = json.loads(resp.read())
            except HTTPError as e:
                self.stdout.write(self.style.WARNING(f"  Skipped ({e.code})"))
                continue

            # Determine the base URL for files in this manifest.
            # pinbase/manifest.json lists files relative to pinbase/.
            manifest_base = base_url
            if "/" in manifest_path:
                manifest_base = f"{base_url}/{manifest_path.rsplit('/', 1)[0]}"

            for entry in manifest:
                rel_path = entry["path"]

                # For the root manifest, only download _NEEDED_FILES.
                # For prefixed manifests, download everything.
                if not local_prefix and rel_path not in _NEEDED_FILES:
                    ignored += 1
                    continue

                expected_size = entry["size"]
                expected_sha = entry["sha256"]
                local_path = os.path.join(dest, local_prefix + rel_path)

                # Skip if local file matches size and checksum
                if (
                    os.path.exists(local_path)
                    and os.path.getsize(local_path) == expected_size
                    and _sha256(local_path) == expected_sha
                ):
                    up_to_date += 1
                    continue

                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                file_url = f"{manifest_base}/{rel_path}"
                self.stdout.write(f"  {local_prefix}{rel_path}")
                with _urlopen(file_url) as resp, open(local_path, "wb") as f:
                    f.write(resp.read())

                # Verify checksum after download
                actual_sha = _sha256(local_path)
                if actual_sha != expected_sha:
                    raise RuntimeError(
                        f"Checksum mismatch for {rel_path}: "
                        f"expected {expected_sha}, got {actual_sha}"
                    )
                downloaded += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {downloaded} downloaded, {up_to_date} up-to-date, {ignored} skipped."
            )
        )
