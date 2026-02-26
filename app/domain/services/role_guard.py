from app.domain.enums import Role


def role_title(role: Role | str) -> str:
    if isinstance(role, str):
        role = Role(role)
    return {
        Role.FOREMAN: "Прораб",
        Role.PDO: "ПДО",
        Role.PROCUREMENT: "Закупка",
        Role.MANAGER: "Руководитель",
        Role.VIEWER: "Зритель",
    }[role]


def is_action_allowed(role: Role, allowed: set[Role]) -> bool:
    return role in allowed
