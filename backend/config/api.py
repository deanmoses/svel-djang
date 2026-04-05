import importlib

from django.apps import apps
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
    from apps.catalog.models import Manufacturer, MachineModel, Person, Title

    return {
        "titles": Title.objects.count(),
        "models": MachineModel.objects.count(),
        "manufacturers": Manufacturer.objects.count(),
        "people": Person.objects.count(),
    }


@api.get("/health", tags=["private"])
def health(request):
    from django.db import connection

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
    "machine-model": "MachineModel",
    "person": "Person",
    "corporate-entity": "CorporateEntity",
    "manufacturer": "Manufacturer",
}


@api.get("/field-constraints/{entity_type}", tags=["private"])
def get_field_constraints(request, entity_type: str):
    """Return numeric field constraints derived from model validators."""
    from apps.catalog import models as catalog_models
    from apps.catalog.api.edit_claims import get_field_constraints as _get

    class_name = _ENTITY_MODEL_MAP.get(entity_type)
    if not class_name:
        raise HttpError(404, f"Unknown entity type: {entity_type}")

    model_class = getattr(catalog_models, class_name)
    return _get(model_class)
