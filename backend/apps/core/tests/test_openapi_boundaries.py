"""Cross-cutting boundary tests for the OpenAPI surface.

These pin conventions defined in
`docs/plans/types/apiboundary/ApiNamingRationalization.md` and the rename
plan that followed it. Targets are the live OpenAPI doc and module
introspection, not text-pattern checks against source files.
"""

from __future__ import annotations

import importlib
import inspect

import pytest
from ninja import Schema

from config.api import api

ALLOWED_SUFFIXES = ("Schema", "Ref")
FORBIDDEN_GENERIC_NAMES = frozenset(
    {
        "Variant",
        "Source",
        "Stats",
        "Recognition",
        "Create",
        "Input",
        "SearchResponse",
        "Ref",
    }
)
ALLOWED_BARE_NAMES = frozenset({"JsonBody"})

MUTATING_METHODS = frozenset({"post", "patch", "delete"})

# Mutating endpoints that legitimately have no 4xx response. Adding to this
# allowlist requires justification.
NO_4XX_ALLOWLIST = frozenset(
    {
        # Logout takes no body, can't fail validation, returns
        # AuthStatusSchema unconditionally.
        ("/api/auth/logout/", "post"),
    }
)

# Per-app baselines for inline-schema regression check. Schemas should live
# in `schemas.py`, but pre-existing inline definitions are grandfathered.
# The test fails if any app's count grows beyond its baseline; lowering a
# baseline (i.e. migrating inline schemas into schemas.py) is welcome.
INLINE_SCHEMA_BASELINES = {
    "apps.accounts.api": 4,
    "apps.citation.api": 15,
    "apps.media.api": 4,
    "apps.provenance.api": 8,
}


class TestSchemaSuffixDiscipline:
    """Every name in components.schemas conforms to the rationalized rules."""

    @pytest.fixture(scope="class")
    def schema_names(self) -> list[str]:
        return list(api.get_openapi_schema()["components"]["schemas"].keys())

    def test_all_names_use_allowed_suffix_or_bare(self, schema_names: list[str]):
        violations = [
            name
            for name in schema_names
            if name not in ALLOWED_BARE_NAMES and not name.endswith(ALLOWED_SUFFIXES)
        ]
        assert not violations, (
            "Every component schema name must end in 'Schema' or 'Ref', or "
            f"be one of {sorted(ALLOWED_BARE_NAMES)}. Violations: {violations}"
        )

    def test_no_in_or_out_suffix(self, schema_names: list[str]):
        violations = [name for name in schema_names if name.endswith(("In", "Out"))]
        assert not violations, (
            "Schema names must not end in 'In' or 'Out' (use 'Input' or a "
            f"role suffix instead). Violations: {violations}"
        )

    def test_no_forbidden_generic_names(self, schema_names: list[str]):
        violations = sorted(set(schema_names) & FORBIDDEN_GENERIC_NAMES)
        assert not violations, (
            "These generic names were eliminated by the rename and must not "
            f"reappear in components.schemas: {violations}"
        )


class TestInlineSchemaRegression:
    """Schemas should live in schemas.py, not inline in endpoint files.

    Pre-existing inline definitions are grandfathered via per-app baselines.
    The test fails if any app's inline count grows; new schemas must go in
    schemas.py.
    """

    @pytest.mark.parametrize(
        ("module_path", "baseline"), sorted(INLINE_SCHEMA_BASELINES.items())
    )
    def test_inline_schema_count_does_not_grow(self, module_path: str, baseline: int):
        module = importlib.import_module(module_path)
        inline = [
            name
            for name, obj in inspect.getmembers(module, inspect.isclass)
            if obj.__module__ == module_path and issubclass(obj, Schema)
        ]
        assert len(inline) <= baseline, (
            f"{module_path} has {len(inline)} inline Schema classes "
            f"(baseline: {baseline}). New schemas must be defined in "
            f"the app's schemas.py instead. Inline classes found: "
            f"{sorted(inline)}"
        )


class TestMutatingEndpointsHave4xx:
    """Every mutating endpoint declares at least one 4xx response.

    `ValidationErrorSchema` and `RateLimitErrorSchema` give the frontend
    typed access to error bodies; this test ensures mutating endpoints
    actually wire them in (or some other 4xx).
    """

    def test_post_patch_delete_declare_4xx_responses(self):
        paths = api.get_openapi_schema()["paths"]
        violations: list[tuple[str, str]] = []
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method not in MUTATING_METHODS:
                    continue
                if (path, method) in NO_4XX_ALLOWLIST:
                    continue
                response_codes = operation.get("responses", {}).keys()
                if not any(400 <= int(code) < 500 for code in response_codes):
                    violations.append((path, method))
        assert not violations, (
            "These mutating endpoints declare no 4xx response. Add typed "
            "error responses (ValidationErrorSchema, RateLimitErrorSchema, "
            "etc.) or add to NO_4XX_ALLOWLIST with justification: "
            f"{violations}"
        )
