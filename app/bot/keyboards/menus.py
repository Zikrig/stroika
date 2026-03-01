import math
from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

if TYPE_CHECKING:
    from app.domain.enums import Role

PAGE_SIZE = 5


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


def private_main_menu_inline(
    role: "Role | None" = None,
    is_admin: bool = False,
) -> InlineKeyboardMarkup:
    from app.domain.enums import Role
    rows: list[list[InlineKeyboardButton]] = []
    # Активные заявки и Архив — у всех; Новая заявка — только у прораба
    rows = [
        [
            InlineKeyboardButton(text="Активные заявки", callback_data="pm:active"),
            InlineKeyboardButton(text="Архив", callback_data="pm:archive"),
        ],
        [
            InlineKeyboardButton(text="Поиск заявки", callback_data="pm:search"),
            InlineKeyboardButton(text="История заявки", callback_data="pm:history"),
        ],
    ]
    if role == Role.FOREMAN:
        rows.insert(0, [InlineKeyboardButton(text="Новая заявка", callback_data="pm:new_request")])
    if is_admin:
        rows.append([
            InlineKeyboardButton(text="Сменить мою роль", callback_data="admin_menu:set_my_role"),
            InlineKeyboardButton(text="Роли", callback_data="admin_menu:set_help"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def request_list_inline(
    items: list[dict],
    page: int,
    total: int,
    list_type: str,
    chat_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Paginated list. list_type 'a'|'r'. If chat_id set, list is by object (for non-foreman)."""
    suf = f":{chat_id}" if chat_id is not None else ""
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        code = item.get("request_code", "?")
        desc = item.get("name_from_foreman") or item.get("object_name") or ""
        if len(desc) > 30:
            desc = desc[:27] + "..."
        rows.append([
            InlineKeyboardButton(
                text=f"{code} — {desc}",
                callback_data=f"vreq:{list_type}:{page}:{code}{suf}",
            )
        ])
    nav: list[InlineKeyboardButton] = []
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    if page > 0:
        nav.append(InlineKeyboardButton(text="← Назад", callback_data=f"rlist:{list_type}:{page - 1}{suf}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text="Далее →", callback_data=f"rlist:{list_type}:{page + 1}{suf}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="← Меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def request_view_inline(
    request: dict, can_edit: bool, list_type: str, page: int, chat_id: int | None = None,
) -> InlineKeyboardMarkup:
    """Buttons shown when viewing a single request card in DM."""
    code = request["request_code"]
    suf = f":{chat_id}" if chat_id is not None else ""
    rows: list[list[InlineKeyboardButton]] = []
    if can_edit:
        rows.append([
            InlineKeyboardButton(text="✏️ Описание", callback_data=f"ed:d:{code}"),
            InlineKeyboardButton(text="✏️ Кол-во", callback_data=f"ed:q:{code}"),
        ])
        rows.append([
            InlineKeyboardButton(text="✏️ Подобъект", callback_data=f"ed:s:{code}"),
            InlineKeyboardButton(text="✏️ Срок", callback_data=f"ed:n:{code}"),
        ])
    rows.append([InlineKeyboardButton(text="← К списку", callback_data=f"rlist:{list_type}:{page}{suf}")])
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
