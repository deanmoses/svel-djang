"""Shared Ninja schemas reused across apps."""

from __future__ import annotations

from ninja import Schema


class ErrorDetailSchema(Schema):
    """Plain 422 / 404 / 409 / 403 error body: just a ``detail`` string.

    The shared shape used for non-structured failures across endpoints.
    Structured 422s (with ``field_errors`` / ``form_errors``) come from
    :class:`apps.catalog.api.edit_claims.StructuredValidationError` and have
    their own wire format; this schema covers the simpler "detail only" case.
    """

    detail: str


class ValidationErrorBodySchema(Schema):
    message: str
    field_errors: dict[str, str]
    form_errors: list[str]


class ValidationErrorSchema(Schema):
    """Structured 422 body produced by ``StructuredValidationError`` and by
    Ninja's malformed-body handler (see ``config/api.py``)."""

    detail: ValidationErrorBodySchema


class RateLimitErrorBodySchema(Schema):
    message: str
    bucket: str
    retry_after: int


class RateLimitErrorSchema(Schema):
    """Structured 429 body produced by ``RateLimitExceededError``."""

    detail: RateLimitErrorBodySchema


class LinkTypeSchema(Schema):
    """One entry in the autocomplete type picker."""

    name: str
    label: str
    description: str
    flow: str


class LinkTargetSchema(Schema):
    """Serialized shape for one autocomplete result.

    Returned by ``LinkType.autocomplete_serialize`` and consumed by the
    ``/link-types/targets/`` endpoint.
    """

    ref: str
    label: str


class LinkTargetListSchema(Schema):
    """Response body for ``/link-types/targets/``."""

    results: list[LinkTargetSchema]
