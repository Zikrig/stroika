from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def cancel_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel_flow")]]
    )


def new_request_description_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Добавить еще", callback_data="newreq_add_more"),
                InlineKeyboardButton(text="Далее", callback_data="newreq_next"),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_flow")],
        ]
    )


def private_main_menu_inline(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Новая заявка", callback_data="pm:new_request")],
        [
            InlineKeyboardButton(text="Активные заявки", callback_data="pm:active"),
            InlineKeyboardButton(text="Архив", callback_data="pm:archive"),
        ],
        [
            InlineKeyboardButton(text="Поиск заявки", callback_data="pm:search"),
            InlineKeyboardButton(text="История заявки", callback_data="pm:history"),
        ],
    ]
    if is_admin:
        rows.append([
            InlineKeyboardButton(text="Сменить мою роль", callback_data="admin_menu:set_my_role"),
            InlineKeyboardButton(text="Роли", callback_data="admin_menu:set_help"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def object_picker_inline(chats: list[dict], callback_prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for chat in chats:
        rows.append([
            InlineKeyboardButton(
                text=chat["title"],
                callback_data=f"{callback_prefix}:{chat['id']}",
            )
        ])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_flow")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def role_picker_inline() -> InlineKeyboardMarkup:
    roles = [
        ("Прораб", "foreman"),
        ("ПДО", "pdo"),
        ("Закупка", "procurement"),
        ("Руководитель", "manager"),
        ("Зритель", "viewer"),
    ]
    rows = [[InlineKeyboardButton(text=title, callback_data=f"pick_role:{code}")] for title, code in roles]
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_flow")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
