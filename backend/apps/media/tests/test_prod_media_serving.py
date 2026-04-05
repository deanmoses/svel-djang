from __future__ import annotations

from importlib import reload

import pytest
from django.test import Client, override_settings
from django.urls import clear_url_caches

from apps.media.tests.test_dev_media_serving import PNG_BYTES, _write_file


@pytest.mark.django_db
@override_settings(
    DEBUG=False,
    MEDIA_ROOT=None,
    MEDIA_PUBLIC_BASE_URL="/media/",
    MEDIA_URL="/media/",
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    },
)
def test_production_serves_local_media_when_filesystem_storage_is_enabled(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    _write_file(tmp_path, "media/abc/thumb", PNG_BYTES)

    import config.urls as urls_module

    clear_url_caches()
    reload(urls_module)

    try:
        client = Client()
        response = client.get("/media/media/abc/thumb")
        response.close()
    finally:
        clear_url_caches()
        reload(urls_module)

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
