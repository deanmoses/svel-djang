"""Licensing helpers for display threshold and effective license resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.core.models import License

# Maps Constance CONTENT_DISPLAY_POLICY choices to minimum permissiveness_rank.
DISPLAY_POLICY_RANKS: dict[str, int] = {
    "show-all": 0,  # Everything, including Not Allowed
    "include-unknown": 5,  # Unknown (null, rank 5) + all licensed content
    "licensed-only": 38,  # Lowest CC license (CC BY-NC-ND 2.0) and above
}

# Effective rank for null (unknown) license.
UNKNOWN_LICENSE_RANK = 5


def get_minimum_display_rank() -> int:
    """Return the current minimum permissiveness_rank for displaying content."""
    from constance import config

    return DISPLAY_POLICY_RANKS.get(config.CONTENT_DISPLAY_POLICY, 38)


def effective_rank(license_obj: License | None) -> int:
    """Return the permissiveness_rank for a license, or UNKNOWN_LICENSE_RANK if null."""
    if license_obj is None:
        return UNKNOWN_LICENSE_RANK
    return license_obj.permissiveness_rank


def is_displayable(license_obj: License | None) -> bool:
    """Check if content with the given license meets the current display threshold."""
    return effective_rank(license_obj) >= get_minimum_display_rank()


# Image field names that get license metadata denormalized into extra_data.
IMAGE_FIELDS = frozenset({"opdb.images", "ipdb.image_urls", "image_urls"})


def build_source_field_license_map() -> dict[tuple[int, str], License | None]:
    """Prefetch all SourceFieldLicense rows into a lookup dict.

    Returns {(source_id, field_name): license_obj}.
    """
    from apps.provenance.models import SourceFieldLicense

    return {
        (sfl.source_id, sfl.field_name): sfl.license
        for sfl in SourceFieldLicense.objects.select_related("license").all()
    }


def ensure_licenses() -> int:
    """Create canonical license records if they don't exist. Returns count created."""
    from apps.core.models import License

    created = 0
    for data in _CANONICAL_LICENSES:
        _, was_created = License.objects.get_or_create(slug=data["slug"], defaults=data)
        if was_created:
            created += 1
    return created


_CANONICAL_LICENSES = [
    # Public Domain & CC0
    {
        "slug": "public-domain",
        "name": "Public Domain",
        "spdx_id": None,
        "short_name": "Public Domain",
        "url": "",
        "allows_display": True,
        "requires_attribution": False,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 100,
    },
    {
        "slug": "cc0-1-0",
        "name": "Creative Commons Zero 1.0 Universal",
        "spdx_id": "CC0-1.0",
        "short_name": "CC0 1.0",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "allows_display": True,
        "requires_attribution": False,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 99,
    },
    # GFDL
    {
        "slug": "gfdl-1-3",
        "name": "GNU Free Documentation License 1.3",
        "spdx_id": "GFDL-1.3-or-later",
        "short_name": "GFDL 1.3",
        "url": "https://www.gnu.org/licenses/fdl-1.3.html",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": True,
        "permissiveness_rank": 82,
    },
    # CC 4.0 (International)
    {
        "slug": "cc-by-4-0",
        "name": "Creative Commons Attribution 4.0 International",
        "spdx_id": "CC-BY-4.0",
        "short_name": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 90,
    },
    {
        "slug": "cc-by-sa-4-0",
        "name": "Creative Commons Attribution-ShareAlike 4.0 International",
        "spdx_id": "CC-BY-SA-4.0",
        "short_name": "CC BY-SA 4.0",
        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": True,
        "permissiveness_rank": 85,
    },
    {
        "slug": "cc-by-nc-4-0",
        "name": "Creative Commons Attribution-NonCommercial 4.0 International",
        "spdx_id": "CC-BY-NC-4.0",
        "short_name": "CC BY-NC 4.0",
        "url": "https://creativecommons.org/licenses/by-nc/4.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 70,
    },
    {
        "slug": "cc-by-nc-sa-4-0",
        "name": "Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International",
        "spdx_id": "CC-BY-NC-SA-4.0",
        "short_name": "CC BY-NC-SA 4.0",
        "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": True,
        "requires_share_alike": True,
        "permissiveness_rank": 65,
    },
    {
        "slug": "cc-by-nd-4-0",
        "name": "Creative Commons Attribution-NoDerivatives 4.0 International",
        "spdx_id": "CC-BY-ND-4.0",
        "short_name": "CC BY-ND 4.0",
        "url": "https://creativecommons.org/licenses/by-nd/4.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": False,
        "requires_share_alike": False,
        "permissiveness_rank": 50,
    },
    {
        "slug": "cc-by-nc-nd-4-0",
        "name": "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International",
        "spdx_id": "CC-BY-NC-ND-4.0",
        "short_name": "CC BY-NC-ND 4.0",
        "url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": False,
        "requires_share_alike": False,
        "permissiveness_rank": 40,
    },
    # CC 3.0 (Unported)
    {
        "slug": "cc-by-3-0",
        "name": "Creative Commons Attribution 3.0 Unported",
        "spdx_id": "CC-BY-3.0",
        "short_name": "CC BY 3.0",
        "url": "https://creativecommons.org/licenses/by/3.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 89,
    },
    {
        "slug": "cc-by-sa-3-0",
        "name": "Creative Commons Attribution-ShareAlike 3.0 Unported",
        "spdx_id": "CC-BY-SA-3.0",
        "short_name": "CC BY-SA 3.0",
        "url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": True,
        "permissiveness_rank": 84,
    },
    {
        "slug": "cc-by-nc-3-0",
        "name": "Creative Commons Attribution-NonCommercial 3.0 Unported",
        "spdx_id": "CC-BY-NC-3.0",
        "short_name": "CC BY-NC 3.0",
        "url": "https://creativecommons.org/licenses/by-nc/3.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 69,
    },
    {
        "slug": "cc-by-nc-sa-3-0",
        "name": "Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported",
        "spdx_id": "CC-BY-NC-SA-3.0",
        "short_name": "CC BY-NC-SA 3.0",
        "url": "https://creativecommons.org/licenses/by-nc-sa/3.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": True,
        "requires_share_alike": True,
        "permissiveness_rank": 64,
    },
    {
        "slug": "cc-by-nd-3-0",
        "name": "Creative Commons Attribution-NoDerivatives 3.0 Unported",
        "spdx_id": "CC-BY-ND-3.0",
        "short_name": "CC BY-ND 3.0",
        "url": "https://creativecommons.org/licenses/by-nd/3.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": False,
        "requires_share_alike": False,
        "permissiveness_rank": 49,
    },
    {
        "slug": "cc-by-nc-nd-3-0",
        "name": "Creative Commons Attribution-NonCommercial-NoDerivatives 3.0 Unported",
        "spdx_id": "CC-BY-NC-ND-3.0",
        "short_name": "CC BY-NC-ND 3.0",
        "url": "https://creativecommons.org/licenses/by-nc-nd/3.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": False,
        "requires_share_alike": False,
        "permissiveness_rank": 39,
    },
    # CC 2.0 (Generic)
    {
        "slug": "cc-by-2-0",
        "name": "Creative Commons Attribution 2.0 Generic",
        "spdx_id": "CC-BY-2.0",
        "short_name": "CC BY 2.0",
        "url": "https://creativecommons.org/licenses/by/2.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 88,
    },
    {
        "slug": "cc-by-sa-2-0",
        "name": "Creative Commons Attribution-ShareAlike 2.0 Generic",
        "spdx_id": "CC-BY-SA-2.0",
        "short_name": "CC BY-SA 2.0",
        "url": "https://creativecommons.org/licenses/by-sa/2.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": True,
        "requires_share_alike": True,
        "permissiveness_rank": 83,
    },
    {
        "slug": "cc-by-nc-2-0",
        "name": "Creative Commons Attribution-NonCommercial 2.0 Generic",
        "spdx_id": "CC-BY-NC-2.0",
        "short_name": "CC BY-NC 2.0",
        "url": "https://creativecommons.org/licenses/by-nc/2.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": True,
        "requires_share_alike": False,
        "permissiveness_rank": 68,
    },
    {
        "slug": "cc-by-nc-sa-2-0",
        "name": "Creative Commons Attribution-NonCommercial-ShareAlike 2.0 Generic",
        "spdx_id": "CC-BY-NC-SA-2.0",
        "short_name": "CC BY-NC-SA 2.0",
        "url": "https://creativecommons.org/licenses/by-nc-sa/2.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": True,
        "requires_share_alike": True,
        "permissiveness_rank": 63,
    },
    {
        "slug": "cc-by-nd-2-0",
        "name": "Creative Commons Attribution-NoDerivatives 2.0 Generic",
        "spdx_id": "CC-BY-ND-2.0",
        "short_name": "CC BY-ND 2.0",
        "url": "https://creativecommons.org/licenses/by-nd/2.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": False,
        "allows_derivatives": False,
        "requires_share_alike": False,
        "permissiveness_rank": 48,
    },
    {
        "slug": "cc-by-nc-nd-2-0",
        "name": "Creative Commons Attribution-NonCommercial-NoDerivatives 2.0 Generic",
        "spdx_id": "CC-BY-NC-ND-2.0",
        "short_name": "CC BY-NC-ND 2.0",
        "url": "https://creativecommons.org/licenses/by-nc-nd/2.0/",
        "allows_display": True,
        "requires_attribution": True,
        "restricts_commercial": True,
        "allows_derivatives": False,
        "requires_share_alike": False,
        "permissiveness_rank": 38,
    },
    # Policy
    {
        "slug": "not-allowed",
        "name": "Not Allowed",
        "spdx_id": None,
        "short_name": "Not Allowed",
        "url": "",
        "allows_display": False,
        "requires_attribution": False,
        "restricts_commercial": False,
        "allows_derivatives": False,
        "requires_share_alike": False,
        "permissiveness_rank": 0,
    },
]


def resolve_effective_license(
    claim,
    sfl_map: dict[tuple[int, str], License | None] | None = None,
) -> License | None:
    """Resolve the effective license for a claim.

    Resolution order:
    1. claim.license (per-claim override)
    2. SourceFieldLicense for (claim.source, claim.field_name)
    3. claim.source.default_license (source-wide default)
    4. None (unknown)
    """
    if claim.license_id:
        return claim.license
    if claim.source_id:
        if sfl_map is not None:
            sfl_license = sfl_map.get((claim.source_id, claim.field_name))
            if sfl_license:
                return sfl_license
        return claim.source.default_license if claim.source else None
    return None
