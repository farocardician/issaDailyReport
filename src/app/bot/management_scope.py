from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.roles import Role, can_manage_admins, can_manage_users
from app.domain.session_state import Step


@dataclass(frozen=True)
class ManagementScope:
    name: str
    root_step: Step
    managed_role: Role
    can_manage: Callable[[Role], bool]
    block_self: bool
    entity: str
    entity_plural: str

    @property
    def menu_key(self) -> str:
        return f"MANAGE_{self.entity_plural}_MENU"

    def key(self, suffix: str) -> str:
        return f"{self.entity}_{suffix}"


SCOPE_USERS = ManagementScope(
    name="users",
    root_step=Step.MANAGE_USERS_MENU,
    managed_role=Role.USER,
    can_manage=can_manage_users,
    block_self=False,
    entity="USER",
    entity_plural="USERS",
)

SCOPE_ADMINS = ManagementScope(
    name="admins",
    root_step=Step.MANAGE_ADMINS_MENU,
    managed_role=Role.ADMIN,
    can_manage=can_manage_admins,
    block_self=True,
    entity="ADMIN",
    entity_plural="ADMINS",
)

_SCOPES_BY_NAME = {
    SCOPE_USERS.name: SCOPE_USERS,
    SCOPE_ADMINS.name: SCOPE_ADMINS,
}


def scope_from_callback(data: str) -> ManagementScope | None:
    return _SCOPES_BY_NAME.get(data.split(":", 1)[0])


def scope_from_draft(draft: dict[str, Any]) -> ManagementScope | None:
    return _SCOPES_BY_NAME.get(str(draft.get("mgmt_scope", "")))
