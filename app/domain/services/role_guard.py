from app.domain.enums import Role


_ROLE_EMOJI = {
    Role.FOREMAN: "👷",
    Role.PDO: "🧮",
    Role.PROCUREMENT: "🛒",
    Role.MANAGER: "👔",
    Role.VIEWER: "👀",
}

_ROLE_NAME_RU = {
    Role.FOREMAN: "Прораб",
    Role.PDO: "ПДО",
    Role.PROCUREMENT: "Закупка",
    Role.MANAGER: "Руководитель",
    Role.VIEWER: "Зритель",
}


def role_emoji(role: Role | str) -> str:
    if isinstance(role, str):
        role = Role(role)
    return _ROLE_EMOJI[role]


def role_title(role: Role | str) -> str:
    """Human-readable role with emoji prefix, e.g. '👷 Прораб'."""
    if isinstance(role, str):
        role = Role(role)
    return f"{_ROLE_EMOJI[role]} {_ROLE_NAME_RU[role]}"


def is_action_allowed(role: Role, allowed: set[Role]) -> bool:
    return role in allowed
