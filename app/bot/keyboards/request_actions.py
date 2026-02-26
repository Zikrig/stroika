from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.enums import Role, StageCode


def request_actions_keyboard(request: dict, role: Role) -> InlineKeyboardMarkup | None:
    stage = StageCode(request["stage_code"])
    request_id = request["id"]
    buttons: list[list[InlineKeyboardButton]] = []

    if role == Role.PDO and stage in {StageCode.CREATED, StageCode.PDO_PROCESSING}:
        buttons.append([InlineKeyboardButton(text="К заявке", callback_data=f"take_pdo:{request_id}")])
        buttons.append([InlineKeyboardButton(text="Загрузить форму ПДО", callback_data=f"pdo_template:{request_id}")])
        buttons.append([InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{request_id}")])

    if role == Role.PROCUREMENT:
        if stage == StageCode.TRANSFERRED_TO_PROCUREMENT:
            buttons.append([InlineKeyboardButton(text="К заявке", callback_data=f"take_proc:{request_id}")])
        if stage == StageCode.PROCUREMENT_IN_WORK:
            buttons.append([InlineKeyboardButton(text="Закуплено", callback_data=f"purchased:{request_id}")])
            buttons.append([InlineKeyboardButton(text="Вернуть ПДО", callback_data=f"return_pdo:{request_id}")])
            buttons.append([InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{request_id}")])
        if stage == StageCode.PURCHASED:
            buttons.append([InlineKeyboardButton(text="Отгружено", callback_data=f"shipped:{request_id}")])
            buttons.append([InlineKeyboardButton(text="Вернуть ПДО", callback_data=f"return_pdo:{request_id}")])

    if role == Role.FOREMAN:
        if stage in {StageCode.CREATED}:
            buttons.append([InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{request_id}")])
        if stage in {StageCode.SHIPPED, StageCode.PARTIALLY_RECEIVED}:
            buttons.append([InlineKeyboardButton(text="Получено частично", callback_data=f"received_partial:{request_id}")])
            buttons.append([InlineKeyboardButton(text="Получено полностью", callback_data=f"received_full:{request_id}")])
            buttons.append([InlineKeyboardButton(text="Повторить заявку", callback_data=f"repeat:{request_id}")])

    if role == Role.MANAGER:
        buttons.append([InlineKeyboardButton(text="Комментарий", callback_data=f"mgr_comment:{request_id}")])
        if stage != StageCode.PAUSED:
            buttons.append([InlineKeyboardButton(text="Пауза", callback_data=f"pause:{request_id}")])
        else:
            buttons.append([InlineKeyboardButton(text="Снять паузу", callback_data=f"resume:{request_id}")])
        buttons.append([InlineKeyboardButton(text="Прекратить закупку", callback_data=f"terminate:{request_id}")])

    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)
