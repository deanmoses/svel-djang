import argparse
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from config.api import api


class Command(BaseCommand):
    help = "Export the OpenAPI schema to a JSON file"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-o",
            "--output",
            default=str(
                Path(__file__).resolve().parent.parent.parent.parent / "openapi.json"
            ),
            help="Output file path (default: backend/openapi.json)",
        )

    def handle(self, *args: object, **options: Any) -> None:
        schema = api.get_openapi_schema()
        output_path = Path(options["output"])
        output_path.write_text(json.dumps(schema, indent=2))
        self.stdout.write(
            self.style.SUCCESS(f"OpenAPI schema exported to {output_path}")
        )
