"""Auth & user API endpoints."""

from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from ninja import Router, Schema

from apps.provenance.entity_resolution import batch_resolve_entities
from apps.provenance.models import ChangeSet, Claim

from .models import UserProfile
from .workos_client import get_workos_client

log = logging.getLogger(__name__)

User = get_user_model()

auth_router = Router(tags=["auth", "private"])
user_page_router = Router(tags=["private"])


# ── Schemas ──────────────────────────────────────────────────────────


class AuthStatusSchema(Schema):
    is_authenticated: bool
    id: int | None = None
    username: str | None = None


class _ErrorSchema(Schema):
    detail: str


class EntityContributionSchema(Schema):
    entity_href: str
    entity_name: str
    entity_type_label: str
    edit_count: int
    last_edited_at: str


class UserChangeSetSchema(Schema):
    id: int
    note: str
    created_at: str
    entity_href: str
    entity_name: str
    entity_type_label: str


class UserProfileSchema(Schema):
    username: str
    member_since: str
    edit_count: int
    entities_edited: list[EntityContributionSchema]
    recent_edits: list[UserChangeSetSchema]


# ── Helpers ──────────────────────────────────────────────────────────


def _generate_username(email: str) -> str:
    """Derive a unique username from an email address."""
    base = email.split("@")[0]
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


def _get_profile(user) -> UserProfile:
    return UserProfile.objects.get(user=user)


def get_or_create_django_user(workos_user):
    """Match or create a Django User from a WorkOS user profile.

    Matching priority:
    1. By workos_user_id on UserProfile (returning user)
    2. By verified email if exactly one local user matches (links accounts)
    3. Create new user (self-registration)
    """
    # 1. Exact match on WorkOS user ID
    try:
        profile = UserProfile.objects.select_related("user").get(
            workos_user_id=workos_user.id,
        )
        return profile.user
    except UserProfile.DoesNotExist:
        pass

    # 2. Match by verified email — only if unambiguous
    if workos_user.email_verified:
        matches = User.objects.filter(email=workos_user.email)
        if matches.count() == 1:
            user = matches.get()
            profile = _get_profile(user)
            profile.workos_user_id = workos_user.id
            profile.save(update_fields=["workos_user_id"])
            return user

    # 3. Create new user
    user = User.objects.create_user(
        username=_generate_username(workos_user.email),
        email=workos_user.email,
        first_name=workos_user.first_name or "",
        last_name=workos_user.last_name or "",
    )
    # Profile auto-created by post_save signal
    profile = _get_profile(user)
    profile.workos_user_id = workos_user.id
    profile.save(update_fields=["workos_user_id"])
    return user


# ── Endpoints ────────────────────────────────────────────────────────


@auth_router.get("/me/", response=AuthStatusSchema)
def auth_me(request):
    """Return current session's authentication state.

    Always succeeds (no auth required). Returns is_authenticated=False for
    anonymous users.
    """
    if request.user.is_authenticated:
        return {
            "is_authenticated": True,
            "id": request.user.id,
            "username": request.user.username,
        }
    return {"is_authenticated": False}


@auth_router.get("/login/", url_name="workos_login", include_in_schema=False)
def auth_login(request):
    """Redirect to WorkOS AuthKit hosted login UI."""
    if not settings.WORKOS_API_KEY or not settings.WORKOS_CLIENT_ID:
        return HttpResponse(
            "WorkOS is not configured. Set WORKOS_API_KEY and WORKOS_CLIENT_ID.",
            status=503,
        )

    next_url = request.GET.get("next", "/")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        next_url = "/"

    state = secrets.token_urlsafe(32)
    request.session[f"auth_{state}"] = next_url

    try:
        client = get_workos_client()
        authorization_url = client.user_management.get_authorization_url(
            provider="authkit",
            redirect_uri=settings.WORKOS_REDIRECT_URI,
            state=state,
        )
    except Exception:
        log.exception("Failed to generate WorkOS authorization URL")
        return HttpResponse(
            "Sign-in is temporarily unavailable. Please try again later.",
            status=503,
        )
    return HttpResponseRedirect(authorization_url)


@auth_router.get("/callback/", url_name="workos_callback", include_in_schema=False)
def auth_callback(request):
    """Handle the OAuth callback from WorkOS."""
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code or not state:
        return HttpResponseBadRequest("Missing code or state parameter.")

    next_url = request.session.pop(f"auth_{state}", None)
    if next_url is None:
        return HttpResponseBadRequest("Invalid or expired state parameter.")

    try:
        client = get_workos_client()
        auth_response = client.user_management.authenticate_with_code(
            code=code,
        )
    except Exception:
        log.exception("WorkOS code exchange failed")
        return HttpResponseBadRequest(
            "Authentication failed. The login link may have expired — please try again."
        )

    user = get_or_create_django_user(auth_response.user)
    login(request, user, backend="apps.accounts.backends.WorkOSBackend")
    return HttpResponseRedirect(next_url)


@auth_router.post("/logout/", response=AuthStatusSchema)
def auth_logout(request):
    """End the current session."""
    logout(request)
    return {"is_authenticated": False}


@user_page_router.get(
    "/{username}/", response={200: UserProfileSchema, 404: _ErrorSchema}
)
def user_profile_page(request, username: str):
    """Page model for the user profile page: contribution history."""
    user = get_object_or_404(User, username=username)
    profile = _get_profile(user)

    edit_count = ChangeSet.objects.filter(user=user).count()
    member_since = profile.created_at.isoformat()

    entity_rows = list(
        Claim.objects.filter(user=user, changeset__isnull=False)
        .values("content_type_id", "object_id")
        .annotate(
            edit_count=Count("changeset", distinct=True),
            last_edited_at=Max("changeset__created_at"),
        )
        .order_by("-last_edited_at")
    )

    resolved = batch_resolve_entities(entity_rows)

    entities_edited = []
    for row in entity_rows:
        meta = resolved.get((row["content_type_id"], row["object_id"]))
        if not meta:
            continue
        entities_edited.append(
            {
                "entity_href": meta["href"],
                "entity_name": meta["name"],
                "entity_type_label": meta["type_label"],
                "edit_count": row["edit_count"],
                "last_edited_at": row["last_edited_at"].isoformat(),
            }
        )

    recent_changesets = (
        ChangeSet.objects.filter(user=user)
        .prefetch_related("claims")
        .order_by("-created_at")[:50]
    )

    cs_entity_refs: list[dict] = []
    cs_first_claim: dict[int, tuple[int, int]] = {}
    for cs in recent_changesets:
        prefetched_claims = cs.claims.all()
        if prefetched_claims:
            c = prefetched_claims[0]
            key = (c.content_type_id, c.object_id)
            cs_first_claim[cs.pk] = key
            cs_entity_refs.append({"content_type_id": key[0], "object_id": key[1]})

    cs_resolved = batch_resolve_entities(cs_entity_refs)

    recent_edits = []
    for cs in recent_changesets:
        ref = cs_first_claim.get(cs.pk)
        if not ref:
            continue
        meta = cs_resolved.get(ref)
        if not meta:
            continue
        recent_edits.append(
            {
                "id": cs.pk,
                "note": cs.note,
                "created_at": cs.created_at.isoformat(),
                "entity_href": meta["href"],
                "entity_name": meta["name"],
                "entity_type_label": meta["type_label"],
            }
        )

    return {
        "username": user.username,
        "member_since": member_since,
        "edit_count": edit_count,
        "entities_edited": entities_edited,
        "recent_edits": recent_edits,
    }


routers = [
    ("/auth/", auth_router),
    ("/pages/user/", user_page_router),
]
