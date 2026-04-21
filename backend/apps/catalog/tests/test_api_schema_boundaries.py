"""Tests for shared API schema ownership boundaries.

Shared wire shapes should be *defined* in the app that owns the domain
concept, not in `catalog.api.schemas`. Catalog may still import and compose
them (e.g. `ClaimPatchSchema.citation: EditCitationInput | None`), so we
check definition site via `__module__` rather than re-export presence.
"""

from apps.catalog.api import schemas as catalog_schemas
from apps.media import schemas as media_schemas
from apps.provenance import schemas as provenance_schemas


class TestSharedSchemaOwnership:
    def test_provenance_owned_shapes_are_defined_in_provenance(self):
        for name in (
            "EditCitationInput",
            "AttributionSchema",
            "InlineCitationLinkSchema",
            "InlineCitationSchema",
            "RichTextSchema",
        ):
            cls = getattr(provenance_schemas, name)
            assert cls.__module__ == "apps.provenance.schemas", (
                f"{name} should be defined in apps.provenance.schemas, "
                f"got {cls.__module__}"
            )

    def test_media_owned_shapes_are_defined_in_media(self):
        for name in ("MediaRenditionsSchema", "UploadedMediaSchema"):
            cls = getattr(media_schemas, name)
            assert cls.__module__ == "apps.media.schemas", (
                f"{name} should be defined in apps.media.schemas, got {cls.__module__}"
            )

    def test_catalog_schemas_does_not_redefine_shared_shapes(self):
        # Catalog may import and compose these, but must not define them.
        shared_names = (
            "EditCitationInput",
            "AttributionSchema",
            "InlineCitationLinkSchema",
            "InlineCitationSchema",
            "RichTextSchema",
            "MediaRenditionsSchema",
            "UploadedMediaSchema",
        )
        for name in shared_names:
            cls = getattr(catalog_schemas, name, None)
            if cls is None:
                continue
            assert cls.__module__ != "apps.catalog.api.schemas", (
                f"{name} is defined in catalog but should live in its owning app"
            )
