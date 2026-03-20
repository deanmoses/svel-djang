"""Download ingest source files from Cloudflare R2.

Uses only stdlib (urllib.request) so it works on Railway's slim Python image.
Fetches manifest.json, then downloads only the files needed by the ingest
pipeline (IPDB, OPDB, and pinbase_export/).

Usage (local):
    uv run python manage.py pull_ingest_sources --dest ../data/ingest_sources

Usage (Railway):
    .venv/bin/python manage.py pull_ingest_sources --dest /tmp/ingest_sources
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request

from django.core.management.base import BaseCommand

_OPENER = urllib.request.build_opener()
_OPENER.addheaders = [("User-Agent", "pinbase/1.0")]

# Only download files the ingest pipeline needs.
_NEEDED_FILES = {
    "ipdb_xantari.json",
    "opdb_export_machines.json",
    "opdb_changelog.json",
}
_NEEDED_PREFIXES = ("pinbase_export/",)


def _urlopen(url: str):
    return _OPENER.open(url)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


class Command(BaseCommand):
    help = "Download ingest source files from Cloudflare R2."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=os.environ.get(
                "R2_PUBLIC_URL", "https://pub-8f33ea1ac628450298edd0d3243ecf5a.r2.dev"
            ),
            help="Base URL of the R2 public bucket (default: R2_PUBLIC_URL env var).",
        )
        parser.add_argument(
            "--dest",
            default="/tmp/ingest_sources",
            help="Local directory to download into (default: /tmp/ingest_sources).",
        )

    def handle(self, **options):
        base_url = options["url"].rstrip("/")
        dest = options["dest"]

        # Fetch manifest
        manifest_url = f"{base_url}/manifest.json"
        self.stdout.write(f"Fetching manifest from {manifest_url}")
        with _urlopen(manifest_url) as resp:
            manifest = json.loads(resp.read())

        downloaded = 0
        skipped = 0
        ignored = 0

        for entry in manifest:
            rel_path = entry["path"]

            if rel_path not in _NEEDED_FILES and not rel_path.startswith(
                _NEEDED_PREFIXES
            ):
                ignored += 1
                continue
            expected_size = entry["size"]
            expected_sha = entry["sha256"]
            local_path = os.path.join(dest, rel_path)

            # Skip if local file matches size and checksum
            if (
                os.path.exists(local_path)
                and os.path.getsize(local_path) == expected_size
            ):
                if _sha256(local_path) == expected_sha:
                    skipped += 1
                    continue

            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            file_url = f"{base_url}/{rel_path}"
            self.stdout.write(f"  {rel_path}")
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
                f"Done. {downloaded} downloaded, {skipped} up-to-date, {ignored} skipped."
            )
        )
