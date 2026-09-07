"""Contract tests for ``StructuredApiError`` and the shared response handler.

Locks in three invariants future variants depend on:

1. ``__init_subclass__`` rejects subclasses missing ``kind`` or ``status`` at
   class-definition time, so a forgotten attribute fails at import — not on
   the response path in production.
2. Subclass dispatch through django-ninja: an arbitrary subclass raised from
   an endpoint hits the registered ``@api.exception_handler(StructuredApiError)``
   handler, because Ninja matches by ``isinstance``.
3. The response shape: ``{"detail": {"kind": ..., "message": ..., **to_body()}}``
   plus any headers from ``extra_headers()``.
"""

from __future__ import annotations

from typing import Any, override

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import Client, override_settings
from django.urls import path
from ninja import NinjaAPI

from apps.core.exceptions import StructuredApiError


def test_subclass_without_kind_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="must define class attribute 'kind'"):

        class _BadError(StructuredApiError):
            status = 418


def test_subclass_without_status_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="must define class attribute 'status'"):

        class _BadError(StructuredApiError):
            kind = "bad"


# A throwaway subclass exercising every override hook.
class _TeapotError(StructuredApiError):
    kind = "teapot"
    status = 418

    def __init__(self, message: str, *, flavor: str) -> None:
        super().__init__(message)
        self.flavor = flavor

    @override
    def to_body(self) -> dict[str, Any]:
        return {"flavor": self.flavor}

    @override
    def extra_headers(self) -> dict[str, str]:
        return {"X-Teapot": self.flavor}


# Build a dedicated NinjaAPI + URLconf so the handler dispatch is exercised
# end-to-end without polluting the project's main API schema.
_test_api = NinjaAPI(urls_namespace="structured_errors_test")


@_test_api.get("/raise")
def _raise(request: HttpRequest) -> dict[str, str]:
    raise _TeapotError("I'm a teapot.", flavor="earl-grey")


def _handler(
    request: HttpRequest, exc: StructuredApiError | type[StructuredApiError]
) -> HttpResponse:
    from config.api import _structured_error_response

    assert isinstance(exc, StructuredApiError)
    return _structured_error_response(exc)


_test_api.add_exception_handler(StructuredApiError, _handler)


urlpatterns = [path("api/", _test_api.urls)]


@override_settings(ROOT_URLCONF=__name__)
def test_subclass_dispatches_through_base_handler() -> None:
    resp = Client().get("/api/raise")

    assert resp.status_code == 418
    assert resp.json() == {
        "detail": {
            "kind": "teapot",
            "message": "I'm a teapot.",
            "flavor": "earl-grey",
        }
    }
    assert resp["X-Teapot"] == "earl-grey"


def test_production_api_registers_structured_error_handler() -> None:
    """The production ``api`` object must dispatch ``StructuredApiError``
    subclasses through ``_handle_structured_api_error``. Catches a removal
    or shadowing of the base-class handler in ``config/api.py``."""
    from config.api import _handle_structured_api_error, api

    assert (
        api._exception_handlers.get(StructuredApiError) is _handle_structured_api_error
    )
