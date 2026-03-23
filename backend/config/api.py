from django.conf import settings
from ninja import NinjaAPI, Schema

from apps.accounts.api import auth_router
from apps.catalog.api import (
    cabinets_router,
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
api.add_router("/sources/", sources_router)
api.add_router("/review/", review_router)
