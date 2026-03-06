"""Seed all taxonomy models from data/*.json files.

Creates records and asserts claims for claim-controlled fields (name, display_order)
via the "pinbase" source. Description is set directly as editorial content.

Replaces the old ingest_machine_types_seed and ingest_display_types_seed commands.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.catalog.models import (
    Cabinet,
    DisplaySubtype,
    DisplayType,
    Franchise,
    GameFormat,
    GameplayFeature,
    Tag,
    TechnologyGeneration,
    TechnologySubgeneration,
)
from apps.provenance.models import Claim, Source

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parents[5] / "data"

PINBASE_PRIORITY = 300

# Registry: (json_filename, model_class, json_name_key, has_display_order, parent_config)
# parent_config: (model_fk_field, parent_model, json_fk_key) or None
TAXONOMY_REGISTRY = [
    # Top-level (no parent FK) — order matters: parents before children.
    ("technology_generations.json", TechnologyGeneration, "title", True, None),
    ("display_types.json", DisplayType, "title", True, None),
    ("cabinets.json", Cabinet, "name", True, None),
    ("game_formats.json", GameFormat, "name", True, None),
    ("gameplay_features.json", GameplayFeature, "name", True, None),
    ("tags.json", Tag, "name", True, None),
    ("franchises.json", Franchise, "name", False, None),
    # Child models (parents must be seeded first).
    (
        "technology_subgenerations.json",
        TechnologySubgeneration,
        "name",
        True,
        ("technology_generation", TechnologyGeneration, "technology_generation_slug"),
    ),
    (
        "display_subtypes.json",
        DisplaySubtype,
        "name",
        True,
        ("display_type", DisplayType, "display_type_slug"),
    ),
]


class Command(BaseCommand):
    help = "Seed all taxonomy models from data/*.json via the claims system."

    def handle(self, *args, **options):
        source, _ = Source.objects.get_or_create(
            slug="pinbase",
            defaults={
                "name": "Pinbase",
                "source_type": Source.SourceType.EDITORIAL,
                "priority": PINBASE_PRIORITY,
                "description": "Pinbase curated taxonomy data.",
            },
        )

        for (
            json_file,
            model_class,
            name_key,
            has_display_order,
            parent_config,
        ) in TAXONOMY_REGISTRY:
            path = DATA_DIR / json_file
            if not path.exists():
                self.stderr.write(f"  Skipping {json_file} (not found)")
                continue

            count, stats = self._seed_model(
                source, path, model_class, name_key, has_display_order, parent_config
            )
            label = model_class.__name__
            self.stdout.write(
                f"  {label}: {count} records — "
                f"{stats['created']} claims created, "
                f"{stats['unchanged']} unchanged"
            )

        self.stdout.write(self.style.SUCCESS("Taxonomy seed ingestion complete."))

    def _seed_model(
        self, source, path, model_class, name_key, has_display_order, parent_config
    ):
        data = json.loads(path.read_text())
        ct = ContentType.objects.get_for_model(model_class)

        # Resolve parent FK lookup if needed.
        parent_lookup = {}
        if parent_config:
            _, parent_model, _ = parent_config
            parent_lookup = {p.slug: p for p in parent_model.objects.all()}

        # Build model instances from JSON.
        objs = []
        for entry in data:
            slug = entry["slug"]
            name_value = entry[name_key]
            description = entry.get("description", "")
            display_order = entry.get("display_order", 0)

            kwargs: dict = {
                "slug": slug,
                "name": name_value,
                "description": description,
            }
            if has_display_order:
                kwargs["display_order"] = display_order

            if parent_config:
                fk_field, _, json_fk_key = parent_config
                parent_slug = entry[json_fk_key]
                parent_obj = parent_lookup.get(parent_slug)
                if parent_obj is None:
                    logger.warning(
                        "Parent slug %r not found for %s %r — skipping",
                        parent_slug,
                        model_class.__name__,
                        slug,
                    )
                    continue
                kwargs[fk_field] = parent_obj

            objs.append(model_class(**kwargs))

        # Bulk upsert: single INSERT ... ON CONFLICT DO UPDATE.
        update_fields = ["name", "description"]
        if has_display_order:
            update_fields.append("display_order")
        if parent_config:
            fk_field, _, _ = parent_config
            update_fields.append(fk_field)

        objs = model_class.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["slug"],
            update_fields=update_fields,
        )

        # Assert claims for claim-controlled fields.
        pending_claims: list[Claim] = []
        for obj in objs:
            pending_claims.append(
                Claim(
                    content_type_id=ct.pk,
                    object_id=obj.pk,
                    field_name="name",
                    claim_key="name",
                    value=obj.name,
                    citation="",
                )
            )
            if has_display_order:
                pending_claims.append(
                    Claim(
                        content_type_id=ct.pk,
                        object_id=obj.pk,
                        field_name="display_order",
                        claim_key="display_order",
                        value=obj.display_order,
                        citation="",
                    )
                )

        stats = Claim.objects.bulk_assert_claims(source, pending_claims)
        return len(data), stats
