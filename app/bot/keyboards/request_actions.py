from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.enums import Role, StageCode
from app.domain.services.role_guard import role_emoji, role_title


def _format_request_label(request: dict) -> str:
    """ID-15-3 «Коты рыжие» — код + короткое наименование."""
    code = request.get("request_code", "?")
    title = (
        request.get("nomenclature_1c")
        or request.get("name_from_foreman")
        or request.get("object_name")
        or ""
    ).strip()
    if len(title) > 35:
        title = title[:32] + "..."
    return f'{code} «{title}»' if title else code


def _buttons_for_role(request: dict, stage: StageCode, role: Role) -> list[list[InlineKeyboardButton]]:
    """Buttons for a single role at this stage (for DM or single-role use)."""
    out: list[list[InlineKeyboardButton]] = []
    emoji = role_emoji(role)
    request_id = request["id"]
    label = _format_request_label(request)
    if role == Role.PDO and stage in {StageCode.CREATED, StageCode.PDO_PROCESSING}:
        out.append([
            InlineKeyboardButton(
                text=f"{emoji} Загрузить форму ПДО — {label}",
                callback_data=f"pdo_template:{request_id}",
            )
        ])
        out.append([
            InlineKeyboardButton(
                text=f"{emoji} Отменить — {label}",
                callback_data=f"cancel:{request_id}",
            )
        ])
    if role == Role.PROCUREMENT:
        if stage == StageCode.TRANSFERRED_TO_PROCUREMENT:
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} К заявке — {label}",
                    callback_data=f"take_proc:{request_id}",
                )
            ])
        if stage == StageCode.PROCUREMENT_IN_WORK:
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Закуплено — {label}",
                    callback_data=f"purchased:{request_id}",
                )
            ])
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Вернуть ПДО — {label}",
                    callback_data=f"return_pdo:{request_id}",
                )
            ])
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Отменить — {label}",
                    callback_data=f"cancel:{request_id}",
                )
            ])
        if stage == StageCode.PURCHASED:
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Отгружено — {label}",
                    callback_data=f"shipped:{request_id}",
                )
            ])
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Вернуть ПДО — {label}",
                    callback_data=f"return_pdo:{request_id}",
                )
            ])
    if role == Role.FOREMAN:
        if stage in {StageCode.CREATED}:
            out.append([
                InlineKeyboardButton(text=f"{emoji} С кем согласовано? ФИО", callback_data=f"approved_by:{request_id}")
            ])
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Отменить — {label}",
                    callback_data=f"cancel:{request_id}",
                )
            ])
        if stage in {StageCode.SHIPPED, StageCode.PARTIALLY_RECEIVED}:
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Получено частично — {label}",
                    callback_data=f"received_partial:{request_id}",
                )
            ])
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Получено полностью — {label}",
                    callback_data=f"received_full:{request_id}",
                )
            ])
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Повторить заявку — {label}",
                    callback_data=f"repeat:{request_id}",
                )
            ])
    if role == Role.MANAGER:
        out.append([
            InlineKeyboardButton(
                text=f"{emoji} Комментарий — {label}",
                callback_data=f"mgr_comment:{request_id}",
            )
        ])
        if stage != StageCode.PAUSED:
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Пауза — {label}",
                    callback_data=f"pause:{request_id}",
                )
            ])
        else:
            out.append([
                InlineKeyboardButton(
                    text=f"{emoji} Снять паузу — {label}",
                    callback_data=f"resume:{request_id}",
                )
            ])
        out.append([
            InlineKeyboardButton(
                text=f"{emoji} Прекратить закупку — {label}",
                callback_data=f"terminate:{request_id}",
            )
        ])
    return out


def request_actions_keyboard(request: dict, role: Role) -> InlineKeyboardMarkup | None:
    """Keyboard for one role (e.g. in DM after action)."""
    stage = StageCode(request["stage_code"])
    buttons = _buttons_for_role(request, stage, role)
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _format_in_work_label(role_label: str, user: dict | None) -> str:
    """Format 'В работе: Роль (@login)' or 'В работе: Роль (id 123)'."""
    if not user:
        return f"В работе: {role_label}"
    username = user.get("username")
    uid = user.get("id")
    if username:
        return f"В работе: {role_label} (@{username})"
    if uid is not None:
        return f"В работе: {role_label} (id {uid})"
    return f"В работе: {role_label}"


def request_actions_keyboard_group(
    request: dict,
    taken_by_pdo: dict | None = None,
    taken_by_proc: dict | None = None,
) -> InlineKeyboardMarkup | None:
    """Keyboard for group: show buttons for all roles that have actions at this stage.
    Each callback is shown once. After 'К заявке' show 'В работе: ПДО/Закупка (@login or id).'"""
    stage = StageCode(request["stage_code"])
    seen: set[str] = set()
    buttons: list[list[InlineKeyboardButton]] = []
    if stage == StageCode.PDO_PROCESSING:
        label = _format_in_work_label(role_title(Role.PDO), taken_by_pdo)
        buttons.append([InlineKeyboardButton(text=label, callback_data="noop")])
    if stage == StageCode.PROCUREMENT_IN_WORK:
        label = _format_in_work_label(role_title(Role.PROCUREMENT), taken_by_proc)
        buttons.append([InlineKeyboardButton(text=label, callback_data="noop")])
    for role in (Role.PDO, Role.PROCUREMENT, Role.FOREMAN, Role.MANAGER):
        for row in _buttons_for_role(request, stage, role):
            cb = row[0].callback_data
            if cb and cb not in seen:
                seen.add(cb)
                buttons.append(row)
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)
