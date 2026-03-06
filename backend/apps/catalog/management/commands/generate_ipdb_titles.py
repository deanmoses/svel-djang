"""Create Title records for IPDB-only MachineModels that lack a title.

For each IPDB-only model (ipdb_id set, opdb_id NULL) without an active "group"
claim, creates a Title with synthetic opdb_id ``ipdb:{ipdb_id}`` and asserts a
"group" claim linking the model to it.

Models whose names match existing OPDB-backed Titles are flagged with
``needs_review=True`` and contextual notes for human curation.
"""

from __future__ import annotations

import re

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.core.management.base import BaseCommand

from apps.catalog.ingestion.bulk_utils import format_names, generate_unique_slug
from apps.catalog.models import MachineModel, Title
from apps.provenance.models import Claim, Source


def _strip_parenthetical(name: str) -> str:
    """Strip trailing parenthetical from a name, e.g. 'Contact (Junior)' → 'Contact'."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


class Command(BaseCommand):
    help = "Generate Title records for IPDB-only MachineModels without titles."

    def handle(self, *args, **options):
        ct_id = ContentType.objects.get_for_model(MachineModel).pk

        source, _ = Source.objects.update_or_create(
            slug="ipdb",
            defaults={
                "name": "IPDB",
                "source_type": "database",
                "priority": 100,
                "url": "https://www.ipdb.org",
            },
        )

        # Find IPDB-only models: have ipdb_id, no opdb_id.
        ipdb_only = MachineModel.objects.filter(
            ipdb_id__isnull=False, opdb_id__isnull=True
        )

        # Find which of those already have an active "group" claim.
        has_group_claim = set(
            Claim.objects.filter(
                content_type_id=ct_id,
                field_name="group",
                is_active=True,
                source=source,
            ).values_list("object_id", flat=True)
        )

        candidates = [m for m in ipdb_only if m.pk not in has_group_claim]

        if not candidates:
            self.stdout.write("  No IPDB-only models need titles.")
            return

        self.stdout.write(f"  Found {len(candidates)} IPDB-only models without titles.")

        # Build name-match lookup against existing OPDB-backed titles.
        opdb_titles = Title.objects.filter(~Q(opdb_id__startswith="ipdb:"))
        name_to_titles: dict[str, list[Title]] = {}
        for t in opdb_titles:
            name_to_titles.setdefault(t.name.lower(), []).append(t)

        # Pre-fetch existing slugs and synthetic titles for idempotency.
        existing_slugs: set[str] = set(Title.objects.values_list("slug", flat=True))
        existing_synthetic_ids: set[str] = set(
            Title.objects.filter(opdb_id__startswith="ipdb:").values_list(
                "opdb_id", flat=True
            )
        )

        new_titles: list[Title] = []
        pending_claims: list[Claim] = []
        skipped = 0
        flagged = 0

        for model in candidates:
            synthetic_id = f"ipdb:{model.ipdb_id}"

            # Skip if this synthetic title already exists.
            if synthetic_id in existing_synthetic_ids:
                skipped += 1
                continue

            # Check name matches.
            needs_review = False
            needs_review_notes = ""

            exact_matches = name_to_titles.get(model.name.lower(), [])
            if exact_matches:
                needs_review = True
                if len(exact_matches) == 1:
                    t = exact_matches[0]
                    needs_review_notes = (
                        f"Name matches existing title '{t.name}' ({t.opdb_id}). "
                        f"May be a clone/licensee that belongs in that group."
                    )
                else:
                    titles_str = ", ".join(
                        f"'{t.name}' ({t.opdb_id})" for t in exact_matches
                    )
                    needs_review_notes = (
                        f"Name matches multiple existing titles: {titles_str}. "
                        f"Needs manual disambiguation."
                    )
            else:
                # Try base-name match (strip trailing parenthetical).
                base_name = _strip_parenthetical(model.name)
                if base_name != model.name:
                    base_matches = name_to_titles.get(base_name.lower(), [])
                    if base_matches:
                        needs_review = True
                        if len(base_matches) == 1:
                            t = base_matches[0]
                            needs_review_notes = (
                                f"Base name '{base_name}' matches existing title "
                                f"'{t.name}' ({t.opdb_id}). "
                                f"Full name is '{model.name}'."
                            )
                        else:
                            titles_str = ", ".join(
                                f"'{t.name}' ({t.opdb_id})" for t in base_matches
                            )
                            needs_review_notes = (
                                f"Base name '{base_name}' matches multiple existing "
                                f"titles: {titles_str}. "
                                f"Full name is '{model.name}'."
                            )

            if needs_review:
                flagged += 1

            slug = generate_unique_slug(model.name, existing_slugs)
            new_titles.append(
                Title(
                    opdb_id=synthetic_id,
                    name=model.name,
                    slug=slug,
                    needs_review=needs_review,
                    needs_review_notes=needs_review_notes,
                )
            )

            pending_claims.append(
                Claim(
                    content_type_id=ct_id,
                    object_id=model.pk,
                    field_name="group",
                    claim_key="group",
                    value=synthetic_id,
                    needs_review=needs_review,
                    needs_review_notes=needs_review_notes,
                )
            )

        if new_titles:
            Title.objects.bulk_create(new_titles)

        if pending_claims:
            claim_stats = Claim.objects.bulk_assert_claims(source, pending_claims)
            self.stdout.write(
                f"  Claims: {claim_stats.get('created', 0)} created, "
                f"{claim_stats.get('deactivated', 0)} superseded, "
                f"{claim_stats.get('unchanged', 0)} unchanged"
            )

        created_names = [t.name for t in new_titles]
        self.stdout.write(
            f"  Titles: {len(new_titles)} created, {skipped} already existed, "
            f"{flagged} flagged for review"
        )
        if created_names:
            self.stdout.write(f"  Sample: {format_names(created_names)}")
