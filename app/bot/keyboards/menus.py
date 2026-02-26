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


def group_main_menu_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Новая заявка", callback_data="group_menu:new"),
                InlineKeyboardButton(text="Активные заявки", callback_data="group_menu:active"),
            ],
            [
                InlineKeyboardButton(text="Архивные заявки", callback_data="group_menu:archive"),
                InlineKeyboardButton(text="Поиск заявки", callback_data="group_menu:search"),
            ],
            [
                InlineKeyboardButton(text="История заявки", callback_data="group_menu:history"),
                InlineKeyboardButton(text="ID группы", callback_data="group_menu:chat_id"),
            ],
        ]
    )


def private_admin_menu_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сменить мою роль", callback_data="admin_menu:set_my_role"),
            ],
            [
                InlineKeyboardButton(text="Роли", callback_data="admin_menu:set_help"),
            ],
        ]
    )


def admin_groups_inline(chats: list[dict]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for chat in chats:
        rows.append(
            [InlineKeyboardButton(text=f"{chat['title']} ({chat['id']})", callback_data=f"admin_role:{chat['id']}")]
        )
    if rows:
        rows.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_flow")])
    return InlineKeyboardMarkup(
        inline_keyboard=rows or [[InlineKeyboardButton(text="Группы не найдены", callback_data="admin_role:none")]]
    )


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
