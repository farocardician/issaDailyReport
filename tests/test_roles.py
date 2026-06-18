from app.domain.roles import (
    Role,
    can_manage_admins,
    can_manage_stores,
    can_manage_users,
    menu_step_for_role,
    normalize_role,
)
from app.domain.session_state import Step


def test_normalize_role() -> None:
    assert normalize_role("ADMIN") == Role.ADMIN
    assert normalize_role("admin") == Role.ADMIN
    assert normalize_role(" SUPER_ADMIN ") == Role.SUPER_ADMIN
    assert normalize_role("SUPERADMIN") == Role.SUPER_ADMIN
    assert normalize_role("super_admin") == Role.SUPER_ADMIN
    assert normalize_role("super admin") == Role.SUPER_ADMIN
    assert normalize_role("SPG") == Role.USER
    assert normalize_role("USER") == Role.USER
    assert normalize_role("") == Role.USER
    assert normalize_role(None) == Role.USER
    assert normalize_role("random") == Role.USER


def test_menu_step_for_role() -> None:
    assert menu_step_for_role(Role.USER) is None
    assert menu_step_for_role(Role.ADMIN) == Step.ADMIN_MENU
    assert menu_step_for_role(Role.SUPER_ADMIN) == Step.SUPER_ADMIN_MENU


def test_permission_predicates() -> None:
    assert can_manage_users(Role.USER) is False
    assert can_manage_users(Role.ADMIN) is True
    assert can_manage_users(Role.SUPER_ADMIN) is True

    assert can_manage_admins(Role.USER) is False
    assert can_manage_admins(Role.ADMIN) is False
    assert can_manage_admins(Role.SUPER_ADMIN) is True

    assert can_manage_stores(Role.USER) is False
    assert can_manage_stores(Role.ADMIN) is False
    assert can_manage_stores(Role.SUPER_ADMIN) is True
