"""Claim- and source-aware license resolution."""

from __future__ import annotations

from apps.core.models import License
from apps.provenance.models import Claim, SourceFieldLicense

# Prefetched (source_id, field_name) → license lookup, built once per request
# by build_source_field_license_map() to avoid N+1 queries when resolving
# effective licenses for many claims.
type SourceFieldLicenseMap = dict[tuple[int, str], License | None]


def build_source_field_license_map() -> SourceFieldLicenseMap:
    """Prefetch all SourceFieldLicense rows into a lookup dict.

    Returns {(source_id, field_name): license_obj}.
    """
    return {
        (sfl.source_id, sfl.field_name): sfl.license
        for sfl in SourceFieldLicense.objects.select_related("license").all()
    }


def resolve_effective_license(
    claim: Claim,
    sfl_map: SourceFieldLicenseMap | None = None,
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
