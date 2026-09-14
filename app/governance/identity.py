"""Lightweight demo identity/authorization model.

Not a real authentication platform — deliberately so, per project scope.
Actors identify themselves via a request header (X-ArchGuard-Actor) and a
role-prefix convention (e.g. "approver:jane", "admin:oncall"). This is
sufficient to demonstrate approval accountability and role separation in a
local POC; see docs/SECURITY.md for the honest limitation statement.
"""

from __future__ import annotations

import re

from app.domain.exceptions import UnauthorizedActionError

_ACTOR_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.:-]{1,127}$")


def require_actor(actor: str | None) -> str:
    if not actor or not actor.strip():
        raise UnauthorizedActionError("Missing required actor identity header.")
    actor = actor.strip()
    if not _ACTOR_PATTERN.match(actor):
        raise UnauthorizedActionError("Actor identity has an invalid format.")
    return actor


def require_role(actor: str, allowed_prefixes: tuple[str, ...]) -> str:
    actor = require_actor(actor)
    if not any(actor.startswith(prefix) for prefix in allowed_prefixes):
        raise UnauthorizedActionError(
            f"Actor '{actor}' is not authorized for this action; requires one of role prefixes {allowed_prefixes}."
        )
    return actor
