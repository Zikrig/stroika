from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.enums import Role, StageCode


def _buttons_for_role(request_id: str, stage: StageCode, role: Role) -> list[list[InlineKeyboardButton]]:
    """Buttons for a single role at this stage (for DM or single-role use)."""
    out: list[list[InlineKeyboardButton]] = []
    if role == Role.PDO and stage in {StageCode.CREATED, StageCode.PDO_PROCESSING}:
        out.append([InlineKeyboardButton(text="К заявке", callback_data=f"take_pdo:{request_id}")])
        out.append([InlineKeyboardButton(text="Загрузить форму ПДО", callback_data=f"pdo_template:{request_id}")])
        out.append([InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{request_id}")])
    if role == Role.PROCUREMENT:
        if stage == StageCode.TRANSFERRED_TO_PROCUREMENT:
            out.append([InlineKeyboardButton(text="К заявке", callback_data=f"take_proc:{request_id}")])
        if stage == StageCode.PROCUREMENT_IN_WORK:
            out.append([InlineKeyboardButton(text="Закуплено", callback_data=f"purchased:{request_id}")])
            out.append([InlineKeyboardButton(text="Вернуть ПДО", callback_data=f"return_pdo:{request_id}")])
            out.append([InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{request_id}")])
        if stage == StageCode.PURCHASED:
            out.append([InlineKeyboardButton(text="Отгружено", callback_data=f"shipped:{request_id}")])
            out.append([InlineKeyboardButton(text="Вернуть ПДО", callback_data=f"return_pdo:{request_id}")])
    if role == Role.FOREMAN:
        if stage in {StageCode.CREATED}:
            out.append([InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{request_id}")])
        if stage in {StageCode.SHIPPED, StageCode.PARTIALLY_RECEIVED}:
            out.append([InlineKeyboardButton(text="Получено частично", callback_data=f"received_partial:{request_id}")])
            out.append([InlineKeyboardButton(text="Получено полностью", callback_data=f"received_full:{request_id}")])
            out.append([InlineKeyboardButton(text="Повторить заявку", callback_data=f"repeat:{request_id}")])
    if role == Role.MANAGER:
        out.append([InlineKeyboardButton(text="Комментарий", callback_data=f"mgr_comment:{request_id}")])
        if stage != StageCode.PAUSED:
            out.append([InlineKeyboardButton(text="Пауза", callback_data=f"pause:{request_id}")])
        else:
            out.append([InlineKeyboardButton(text="Снять паузу", callback_data=f"resume:{request_id}")])
        out.append([InlineKeyboardButton(text="Прекратить закупку", callback_data=f"terminate:{request_id}")])
    return out


def request_actions_keyboard(request: dict, role: Role) -> InlineKeyboardMarkup | None:
    """Keyboard for one role (e.g. in DM after action)."""
    stage = StageCode(request["stage_code"])
    request_id = request["id"]
    buttons = _buttons_for_role(request_id, stage, role)
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def request_actions_keyboard_group(request: dict) -> InlineKeyboardMarkup | None:
    """Keyboard for group: show buttons for all roles that have actions at this stage.
    Each callback is shown once (no duplicate labels)."""
    stage = StageCode(request["stage_code"])
    request_id = request["id"]
    seen: set[str] = set()
    buttons: list[list[InlineKeyboardButton]] = []
    for role in (Role.PDO, Role.PROCUREMENT, Role.FOREMAN, Role.MANAGER):
        for row in _buttons_for_role(request_id, stage, role):
            # row is [InlineKeyboardButton]; callback_data is unique per action
            cb = row[0].callback_data
            if cb and cb not in seen:
                seen.add(cb)
                buttons.append(row)
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)
