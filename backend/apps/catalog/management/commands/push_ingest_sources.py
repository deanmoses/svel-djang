"""Push ingest source files to Cloudflare R2.

Regenerates pinbase_export first, builds a manifest with SHA-256 checksums,
then uploads all files using boto3 (S3-compatible API).

Usage (local):
    uv run python manage.py push_ingest_sources

Requires R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
in environment or .env.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

REPO_ROOT = Path(__file__).resolve().parents[5]
INGEST_DIR = REPO_ROOT / "data" / "ingest_sources"
EXCLUDE = {
    "manifest.json",
    "ipdb_database_OLD.json",
    "opbd_machines.json",
    "opdb_groups.json",
    ".DS_Store",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_files(src: Path) -> list[dict]:
    """Walk src and return manifest entries, excluding dotfiles and stale files."""
    entries = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.startswith(".") or f in EXCLUDE:
                continue
            full = Path(root) / f
            rel = full.relative_to(src).as_posix()
            entries.append(
                {
                    "path": rel,
                    "size": full.stat().st_size,
                    "sha256": _sha256(full),
                }
            )
    entries.sort(key=lambda e: e["path"])
    return entries


class Command(BaseCommand):
    help = "Push ingest source files to Cloudflare R2."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-export",
            action="store_true",
            help="Skip regenerating pinbase_export (use existing files).",
        )

    def handle(self, **options):
        try:
            import boto3  # noqa: F811
        except ImportError:
            raise CommandError(
                "boto3 is required for push. Install dev dependencies: uv sync"
            )

        # Validate env vars
        account_id = os.environ.get("R2_ACCOUNT_ID")
        access_key = os.environ.get("R2_ACCESS_KEY_ID")
        secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
        bucket = os.environ.get("R2_BUCKET")

        missing = []
        if not account_id:
            missing.append("R2_ACCOUNT_ID")
        if not access_key:
            missing.append("R2_ACCESS_KEY_ID")
        if not secret_key:
            missing.append("R2_SECRET_ACCESS_KEY")
        if not bucket:
            missing.append("R2_BUCKET")
        if missing:
            raise CommandError(f"Missing env vars: {', '.join(missing)}")

        # Step 1: Regenerate pinbase_export
        if not options["skip_export"]:
            self.stdout.write("Regenerating pinbase_export...")
            export_script = REPO_ROOT / "scripts" / "export_pinbase_json.py"
            result = subprocess.run(
                [sys.executable, str(export_script)],
                cwd=str(REPO_ROOT / "backend"),
            )
            if result.returncode != 0:
                raise CommandError("export_pinbase_json.py failed")

        # Step 2: Build manifest
        self.stdout.write("Building manifest...")
        entries = _collect_files(INGEST_DIR)
        manifest_path = INGEST_DIR / "manifest.json"
        manifest_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(f"  {len(entries)} files in manifest")

        # Step 3: Upload to R2
        self.stdout.write("Uploading to R2...")
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        # Upload files first, manifest last (so consumers never see a
        # manifest referencing objects that haven't been uploaded yet).
        uploaded = 0
        skipped = 0
        for entry in entries:
            local_path = INGEST_DIR / entry["path"]
            key = entry["path"]

            # Skip if remote file matches size AND content hash.
            # R2 ETag is the MD5 hex digest for single-part uploads.
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
                remote_size = head["ContentLength"]
                remote_etag = head["ETag"].strip('"')
                local_md5 = hashlib.md5(local_path.read_bytes()).hexdigest()
                if remote_size == entry["size"] and remote_etag == local_md5:
                    skipped += 1
                    continue
            except s3.exceptions.ClientError:
                pass  # File doesn't exist remotely yet

            self.stdout.write(f"  {key}")
            s3.upload_file(str(local_path), bucket, key)
            uploaded += 1

        # Upload manifest last
        s3.upload_file(str(manifest_path), bucket, "manifest.json")

        self.stdout.write(
            self.style.SUCCESS(f"Done. {uploaded} uploaded, {skipped} unchanged.")
        )
