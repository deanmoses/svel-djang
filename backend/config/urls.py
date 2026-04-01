from pathlib import PurePosixPath

from django.conf import settings
from django.contrib import admin
from django.http import Http404, HttpResponse
from django.urls import URLPattern, URLResolver, path, re_path

from .admin_views import resolve_view
from .api import api

# Extensions that indicate a static asset request. If a request ends with one
# of these and WhiteNoise didn't serve it (file doesn't exist), return 404
# rather than the SPA shell. Uses an explicit set to avoid false positives on
# slugs containing dots (e.g., "acme.co").
_ASSET_EXTENSIONS = {
    ".css",
    ".ico",
    ".jpg",
    ".jpeg",
    ".js",
    ".json",
    ".map",
    ".png",
    ".svg",
    ".ttf",
    ".txt",
    ".webp",
    ".woff",
    ".woff2",
    ".xml",
}


def _serve_html(filepath):
    resp = HttpResponse(filepath.read_bytes(), content_type="text/html")
    # Allow browser caching but always revalidate. ConditionalGetMiddleware
    # adds ETag so repeat requests get a fast 304 Not Modified.
    resp["Cache-Control"] = "no-cache"
    return resp


def frontend_spa(request, path=""):
    """Serve the SvelteKit SPA shell for client-side routing.

    WhiteNoise handles requests for physical files (JS bundles, CSS, images).
    This catch-all serves HTML for all other routes, trying prerendered pages
    first, then falling back to the SPA shell (200.html).
    """
    build_dir = settings.FRONTEND_BUILD_DIR

    # Missing static assets should 404, not serve the SPA shell
    suffix = PurePosixPath(path).suffix
    if suffix and suffix in _ASSET_EXTENSIONS:
        raise Http404

    # Root path: serve prerendered index.html (homepage)
    if not path:
        index = build_dir / "index.html"
        if index.is_file():
            return _serve_html(index)

    # Try prerendered HTML: path.html (trailingSlash: 'never', the default)
    if path:
        prerendered = (build_dir / f"{path}.html").resolve()
        if prerendered.is_relative_to(build_dir) and prerendered.is_file():
            return _serve_html(prerendered)

        # Also try path/index.html (trailingSlash: 'always')
        prerendered_dir = (build_dir / path / "index.html").resolve()
        if prerendered_dir.is_relative_to(build_dir) and prerendered_dir.is_file():
            return _serve_html(prerendered_dir)

    # Fall back to SPA shell
    spa_shell = build_dir / "200.html"
    if spa_shell.is_file():
        return _serve_html(spa_shell)

    raise Http404("Frontend not built")


urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/resolve/", resolve_view, name="admin-resolve"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]

# Serve uploaded media files during local development.
if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Catch-all: serve SvelteKit SPA for non-API/admin routes.
# Only active when the frontend build directory exists (i.e., production
# Docker build or after running `pnpm build` locally).
if (
    getattr(settings, "FRONTEND_BUILD_DIR", None)
    and settings.FRONTEND_BUILD_DIR.is_dir()
):
    urlpatterns += [
        re_path(r"^(?!api(?:/|$)|admin(?:/|$))(?P<path>.*)$", frontend_spa),
    ]
