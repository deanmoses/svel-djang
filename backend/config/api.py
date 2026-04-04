from django.conf import settings
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from apps.accounts.api import auth_router, users_router
from apps.catalog.api import (
    cabinets_router,
    corporate_entities_router,
    credit_roles_router,
    display_subtypes_router,
    display_types_router,
    franchises_router,
    game_formats_router,
    gameplay_features_router,
    locations_router,
    manufacturers_router,
    models_router,
    people_router,
    reward_types_router,
    series_router,
    systems_router,
    tags_router,
    technology_generations_router,
    technology_subgenerations_router,
    themes_router,
    titles_router,
)
from apps.core.api import link_types_router
from apps.media.api import media_router
from apps.provenance.api import review_router, sources_router

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
    if not settings.DEBUG:
        if not (settings.FRONTEND_BUILD_DIR / "200.html").is_file():
            raise RuntimeError("Frontend build missing")
    return {"status": "ok"}


api.add_router("/auth/", auth_router)
api.add_router("/users/", users_router)
api.add_router("/corporate-entities/", corporate_entities_router)
api.add_router("/display-types/", display_types_router)
api.add_router("/technology-generations/", technology_generations_router)
api.add_router("/models/", models_router)
api.add_router("/titles/", titles_router)
api.add_router("/manufacturers/", manufacturers_router)
api.add_router("/people/", people_router)
api.add_router("/themes/", themes_router)
api.add_router("/systems/", systems_router)
api.add_router("/series/", series_router)
api.add_router("/franchises/", franchises_router)
api.add_router("/cabinets/", cabinets_router)
api.add_router("/credit-roles/", credit_roles_router)
api.add_router("/display-subtypes/", display_subtypes_router)
api.add_router("/game-formats/", game_formats_router)
api.add_router("/gameplay-features/", gameplay_features_router)
api.add_router("/locations/", locations_router)
api.add_router("/reward-types/", reward_types_router)
api.add_router("/tags/", tags_router)
api.add_router("/technology-subgenerations/", technology_subgenerations_router)
api.add_router("/link-types/", link_types_router)
api.add_router("/sources/", sources_router)
api.add_router("/review/", review_router)
api.add_router("/media/", media_router)


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
