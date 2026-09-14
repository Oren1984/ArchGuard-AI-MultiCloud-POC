from __future__ import annotations

import pytest

from app.domain.exceptions import UnauthorizedActionError
from app.governance.identity import require_actor, require_role


def test_require_actor_accepts_valid_identity():
    assert require_actor("approver:jane") == "approver:jane"


def test_require_actor_rejects_missing():
    with pytest.raises(UnauthorizedActionError):
        require_actor(None)


def test_require_actor_rejects_blank():
    with pytest.raises(UnauthorizedActionError):
        require_actor("   ")


def test_require_actor_rejects_invalid_characters():
    with pytest.raises(UnauthorizedActionError):
        require_actor("bad actor; DROP TABLE events;")


def test_require_role_accepts_matching_prefix():
    assert require_role("admin:oncall", ("admin:",)) == "admin:oncall"


def test_require_role_rejects_non_matching_prefix():
    with pytest.raises(UnauthorizedActionError):
        require_role("viewer:bob", ("admin:", "approver:"))
