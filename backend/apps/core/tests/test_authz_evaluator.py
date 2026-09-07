"""Unit tests for the authz evaluator's decision logic.

Tests the evaluator's behavior in isolation by registering fake
activities under the `isolated_registry` fixture. Real launch
activities are exercised by `test_authz_registry_complete`.
"""

from __future__ import annotations

import pytest

from apps.core.authz.evaluator import check
from apps.core.authz.predicates import email_verified, is_active, is_authenticated
from apps.core.authz.test_factories import StubPolicyUser
from apps.core.authz.types import Activity, Allow, DenialCode, Deny


def _always_deny(code: DenialCode):
    """Helper: build a predicate that always denies with `code`."""

    def predicate(user, target, context):
        return Deny(code)

    return predicate


def _always_allow(user, target, context):
    return Allow()


def test_allow_when_all_predicates_pass(empty_registry):
    empty_registry.register(Activity.CATALOG_EDIT, _always_allow, _always_allow)
    decision = check(StubPolicyUser(), Activity.CATALOG_EDIT)
    assert isinstance(decision, Allow)


def test_deny_when_predicate_fails(empty_registry):
    empty_registry.register(Activity.CATALOG_EDIT, is_authenticated, is_active)
    decision = check(
        StubPolicyUser(is_authenticated=False, is_active=True),
        Activity.CATALOG_EDIT,
    )
    assert isinstance(decision, Deny)
    assert decision.code is DenialCode.AUTH_REQUIRED


def test_priority_picks_most_fundamental_when_multiple_fail(empty_registry):
    """Anonymous + deactivated should yield AUTH_REQUIRED, not ACCOUNT_DEACTIVATED.

    The denial-code priority order exists because telling a deactivated
    user to log in is wrong UX, but telling a logged-out user that their
    account is deactivated is also wrong. AUTH_REQUIRED is more fundamental
    in the priority order, so it wins when both fail.
    """
    empty_registry.register(Activity.CATALOG_EDIT, is_authenticated, is_active)
    decision = check(
        StubPolicyUser(is_authenticated=False, is_active=False),
        Activity.CATALOG_EDIT,
    )
    assert isinstance(decision, Deny)
    assert decision.code is DenialCode.AUTH_REQUIRED


def test_priority_picks_account_deactivated_over_verification(empty_registry):
    """Deactivated + unverified should yield ACCOUNT_DEACTIVATED.

    Account state is more fundamental than verification state — telling
    a deactivated user to verify their email would be misleading. This
    pins VERIFICATION_REQUIRED's priority insertion below ACCOUNT_DEACTIVATED.
    """
    empty_registry.register(Activity.CATALOG_EDIT, is_active, email_verified)
    decision = check(
        StubPolicyUser(is_active=False, is_email_verified=False),
        Activity.CATALOG_EDIT,
    )
    assert isinstance(decision, Deny)
    assert decision.code is DenialCode.ACCOUNT_DEACTIVATED


def test_evaluator_does_not_short_circuit(empty_registry):
    """All predicates must run so priority ordering can see every Deny.

    If the evaluator stopped at the first Deny, this rule — ordered
    [RATE_LIMITED, ACCOUNT_DEACTIVATED] — would return RATE_LIMITED. But
    ACCOUNT_DEACTIVATED is higher-priority and should win.
    """
    empty_registry.register(
        Activity.CATALOG_EDIT,
        _always_deny(DenialCode.RATE_LIMITED),
        _always_deny(DenialCode.ACCOUNT_DEACTIVATED),
    )
    decision = check(StubPolicyUser(), Activity.CATALOG_EDIT)
    assert isinstance(decision, Deny)
    assert decision.code is DenialCode.ACCOUNT_DEACTIVATED


def test_unregistered_activity_raises_lookup_error(empty_registry):
    with pytest.raises(LookupError, match=r"catalog\.edit"):
        check(StubPolicyUser(), Activity.CATALOG_EDIT)
