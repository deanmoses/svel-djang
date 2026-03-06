from django.conf import settings
from ninja import NinjaAPI

from apps.accounts.api import auth_router
from apps.catalog.api import (
    display_types_router,
    franchises_router,
    titles_router,
    manufacturers_router,
    models_router,
    people_router,
    series_router,
    systems_router,
    technology_generations_router,
    themes_router,
)
from apps.provenance.api import review_router, sources_router

api = NinjaAPI(
    title="Pinbase API",
    urls_namespace="api",
)


@api.get("/health")
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
api.add_router("/sources/", sources_router)
api.add_router("/review/", review_router)
