import importlib

from django.apps import apps
from django.db import connection
from django.http import JsonResponse
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

api = NinjaAPI(
    title="Pinbase API",
    urls_namespace="api",
)


# Endpoints tagged "private" are excluded from the public API docs page.
# The API docs expose catalog data endpoints; internal/website endpoints
# (health checks, stats for the homepage, etc.) use tags=["private"].


class StatsSchema(Schema):
    titles: int
    models: int
    manufacturers: int
    people: int


@api.get("/stats", response=StatsSchema, tags=["private"])
def stats(request):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM catalog_title),
                (SELECT COUNT(*) FROM catalog_machinemodel),
                (SELECT COUNT(*) FROM catalog_manufacturer),
                (SELECT COUNT(*) FROM catalog_person)
            """
        )
        titles, models, manufacturers, people = cursor.fetchone()
    return {
        "titles": titles,
        "models": models,
        "manufacturers": manufacturers,
        "people": people,
    }


@api.get("/health", tags=["private"])
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Router autodiscovery — each app's api module exports a `routers` list of
# (prefix, router) tuples.  Adding a new router only requires editing the
# app's own api module; this file never needs to change.
# ---------------------------------------------------------------------------


def _discover_routers():
    for app_config in apps.get_app_configs():
        module_path = f"{app_config.name}.api"
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            if exc.name == module_path:
                continue  # app has no api module — fine
            raise  # broken import inside an existing api module — crash
        for prefix, router in getattr(module, "routers", []):
            api.add_router(prefix, router)


_discover_routers()


# ---------------------------------------------------------------------------
# Structured validation errors — returns field-level + form-level errors
# so the frontend can display inline per-field messages.
# Import is deferred until after router discovery to avoid circular imports.
# ---------------------------------------------------------------------------

from apps.catalog.api.edit_claims import StructuredValidationError  # noqa: E402
from apps.provenance.rate_limits import RateLimitExceeded  # noqa: E402


@api.exception_handler(StructuredValidationError)
def _handle_structured_validation_error(request, exc):
    return JsonResponse({"detail": exc.to_response_body()}, status=422)


@api.exception_handler(RateLimitExceeded)
def _handle_rate_limit_exceeded(request, exc):
    response = JsonResponse(
        {
            "detail": {
                "message": "Rate limit exceeded.",
                "bucket": exc.bucket,
                "retry_after": exc.retry_after,
            }
        },
        status=429,
    )
    response["Retry-After"] = str(exc.retry_after)
    return response


# ---------------------------------------------------------------------------
# Field constraints — single source of truth for numeric validation
# ---------------------------------------------------------------------------


@api.get("/field-constraints/{entity_type}", tags=["private"])
def get_field_constraints(request, entity_type: str):
    """Return numeric field constraints derived from model validators."""
    from apps.catalog.api.edit_claims import get_field_constraints as _get
    from apps.core.entity_types import get_linkable_model

    try:
        model_class = get_linkable_model(entity_type)
    except ValueError:
        raise HttpError(404, f"Unknown entity type: {entity_type}")

    return _get(model_class)
