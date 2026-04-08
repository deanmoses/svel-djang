import importlib

from django.apps import apps
from django.db import connection
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
# Field constraints — single source of truth for numeric validation
# ---------------------------------------------------------------------------

_ENTITY_MODEL_MAP = {
    "model": "MachineModel",
    "person": "Person",
    "corporate-entity": "CorporateEntity",
    "manufacturer": "Manufacturer",
}


@api.get("/field-constraints/{entity_type}", tags=["private"])
def get_field_constraints(request, entity_type: str):
    """Return numeric field constraints derived from model validators."""
    from apps.catalog import models as catalog_models
    from apps.catalog.api.edit_claims import get_field_constraints as _get  # noqa: E402 — deferred to avoid early app import

    class_name = _ENTITY_MODEL_MAP.get(entity_type)
    if not class_name:
        raise HttpError(404, f"Unknown entity type: {entity_type}")

    model_class = getattr(catalog_models, class_name)
    return _get(model_class)
