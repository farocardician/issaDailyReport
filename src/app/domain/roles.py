from enum import StrEnum

from app.domain.session_state import Step


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


def normalize_role(raw: str | None) -> Role:
    value = "_".join(raw.strip().upper().replace("_", " ").split()) if raw is not None else ""
    if value == Role.ADMIN.value:
        return Role.ADMIN
    if value in {Role.SUPER_ADMIN.value, "SUPERADMIN"}:
        return Role.SUPER_ADMIN
    return Role.USER


def menu_step_for_role(role: Role) -> Step | None:
    if role == Role.ADMIN:
        return Step.ADMIN_MENU
    if role == Role.SUPER_ADMIN:
        return Step.SUPER_ADMIN_MENU
    return None


def can_manage_users(role: Role) -> bool:
    return role in {Role.ADMIN, Role.SUPER_ADMIN}


def can_manage_admins(role: Role) -> bool:
    return role == Role.SUPER_ADMIN


def can_manage_stores(role: Role) -> bool:
    return role == Role.SUPER_ADMIN
