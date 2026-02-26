from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.context import AppContext
from app.bot.keyboards.menus import (
    group_main_menu_inline,
    private_admin_menu_inline,
    role_picker_inline,
)
from app.domain.enums import Role
from app.domain.services.role_guard import role_title


def get_router(ctx: AppContext) -> Router:
    router = Router(name="common")

    async def _is_group_admin(chat_id: int, user_id: int, message: Message) -> bool:
        member = await message.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in {"administrator", "creator"}

    async def _is_any_known_group_admin(user_id: int, bot) -> bool:
        chats = await ctx.roles.list_chats()
        for chat in chats:
            try:
                member = await bot.get_chat_member(chat_id=int(chat["id"]), user_id=user_id)
            except Exception:
                continue
            if member.status in {"administrator", "creator"}:
                return True
        return False

    async def _send_private_role_info(message: Message) -> None:
        role = await ctx.roles.get_global_role(message.from_user.id)
        role_text = "не назначена" if role is None else role_title(role)
        await message.bot.send_message(
            chat_id=message.from_user.id,
            text=(
                "Привет!\n"
                "Управление ролями доступно только администраторам группы.\n"
                f"Ваша роль: {role_text}"
            ),
        )

    @router.message(Command("start"))
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        if message.chat.type == "private":
            role = await ctx.roles.get_global_role(message.from_user.id)
            role_text = "не назначена" if role is None else role_title(role)
            is_admin = await _is_any_known_group_admin(message.from_user.id, message.bot)
            reply_markup = private_admin_menu_inline() if is_admin else None
            await message.answer(
                "Бот учёта заявок запущен.\n"
                "Управление из лички на кнопках.\n"
                "Доступные команды: /start, /admin\n"
                f"Ваша роль: {role_text}",
                reply_markup=reply_markup,
            )
            return
        await message.answer(
            "Бот учёта заявок запущен.\n"
            "Используйте кнопки меню.\n"
            "Доступные команды: /start, /admin",
            reply_markup=group_main_menu_inline(),
        )

    @router.message(Command("admin"))
    async def admin(message: Message) -> None:
        if message.chat.type == "private":
            role = await ctx.roles.get_global_role(message.from_user.id)
            is_admin = await _is_any_known_group_admin(message.from_user.id, message.bot)
            if not is_admin:
                role_text = "не назначена" if role is None else role_title(role)
                await message.answer(
                    "Привет!\n"
                    "Управление ролями доступно только администраторам группы.\n"
                    f"Ваша роль: {role_text}"
                )
                return
            if role is None:
                await message.answer("Роль пока не назначена.", reply_markup=private_admin_menu_inline())
                return
            await message.answer(f"Ваша глобальная роль: {role_title(role)}", reply_markup=private_admin_menu_inline())
            return
        if message.chat.type not in {"group", "supergroup"}:
            await message.answer("Команду нужно запускать в служебной группе")
            return
        if not await _is_group_admin(message.chat.id, message.from_user.id, message):
            try:
                await _send_private_role_info(message)
                await message.answer("Написал вам в личку вашу роль.")
            except Exception:
                await message.answer("Не удалось написать в личку. Откройте ЛС с ботом и повторите /admin.")
            return
        role = await ctx.roles.get_role(message.chat.id, message.from_user.id)
        if role is None:
            await message.answer("Роль не назначена. Обратитесь к руководителю или администратору группы")
            return
        await message.answer(f"Ваша роль: {role_title(role)}")

    @router.callback_query(F.data == "admin_menu:set_my_role")
    async def admin_set_my_role(call: CallbackQuery) -> None:
        if not await _is_any_known_group_admin(call.from_user.id, call.bot):
            await call.message.answer("Управление ролями доступно только администраторам группы.")
            await call.answer()
            return
        await call.message.answer("Выберите новую роль для себя:", reply_markup=role_picker_inline())
        await call.answer()

    @router.callback_query(F.data == "admin_menu:set_help")
    async def set_help(call: CallbackQuery) -> None:
        if not await _is_any_known_group_admin(call.from_user.id, call.bot):
            await call.message.answer("Управление ролями доступно только администраторам группы.")
            await call.answer()
            return
        await call.message.answer(
            "Назначение роли другому пользователю:\n"
            "1) В группе ответьте на сообщение пользователя командой /set\n"
            "2) В личку придет сообщение с кнопками ролей\n"
            "3) Нажмите нужную роль",
            reply_markup=private_admin_menu_inline(),
        )
        await call.answer()

    @router.callback_query(F.data == "cancel_flow")
    async def cancel_flow(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        if call.message.chat.type == "private":
            await call.message.answer("Действие отменено.", reply_markup=private_admin_menu_inline())
        else:
            await call.message.answer("Действие отменено.", reply_markup=group_main_menu_inline())
        await call.answer()

    @router.message(Command("set"), F.chat.type.in_({"group", "supergroup"}))
    async def set_role_reply(message: Message) -> None:
        if not await _is_group_admin(message.chat.id, message.from_user.id, message):
            await message.answer("Команда /set доступна только администраторам группы")
            return
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.answer("Команда /set должна быть ответом на сообщение пользователя")
            return

        target = message.reply_to_message.from_user
        await ctx.roles.upsert_chat(message.chat.id, message.chat.title or "Объект")
        await ctx.roles.upsert_user(target.id, target.username, target.full_name)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Прораб", callback_data=f"set_user_role:{target.id}:foreman")],
                [InlineKeyboardButton(text="ПДО", callback_data=f"set_user_role:{target.id}:pdo")],
                [InlineKeyboardButton(text="Закупка", callback_data=f"set_user_role:{target.id}:procurement")],
                [InlineKeyboardButton(text="Руководитель", callback_data=f"set_user_role:{target.id}:manager")],
                [InlineKeyboardButton(text="Зритель", callback_data=f"set_user_role:{target.id}:viewer")],
                [InlineKeyboardButton(text="Отмена", callback_data="cancel_flow")],
            ]
        )

        try:
            await message.bot.send_message(
                chat_id=message.from_user.id,
                text=(
                    f"Назначить роль пользователю {target.full_name} (id={target.id}).\n"
                    "Выберите роль:"
                ),
                reply_markup=keyboard,
            )
            await message.answer("Отправил вам в личку выбор роли.")
        except Exception:
            await message.answer("Не удалось написать вам в личку. Сначала откройте ЛС с ботом и нажмите /start.")

    @router.callback_query(F.data.startswith("set_user_role:"))
    async def set_user_role_pick(call: CallbackQuery) -> None:
        _, user_id_raw, role_raw = call.data.split(":")
        user_id = int(user_id_raw)
        role = Role(role_raw)
        await ctx.roles.upsert_user(user_id, None, f"user_{user_id}")
        await ctx.roles.set_global_role(user_id, role)
        await call.message.answer(f"Роль назначена: user_id={user_id}, role={role_title(role)}")
        await call.answer("Готово")

    @router.callback_query(F.data.startswith("pick_role:"))
    async def set_my_role_pick(call: CallbackQuery) -> None:
        if not await _is_any_known_group_admin(call.from_user.id, call.bot):
            await call.message.answer("Управление ролями доступно только администраторам группы.")
            await call.answer()
            return
        role_raw = call.data.split(":", maxsplit=1)[1]
        role = Role(role_raw)
        await ctx.roles.upsert_user(call.from_user.id, call.from_user.username, call.from_user.full_name)
        await ctx.roles.set_global_role(call.from_user.id, role)
        await call.message.answer(f"Ваша роль обновлена: {role_title(role)}", reply_markup=private_admin_menu_inline())
        await call.answer("Роль сохранена")

    @router.message(F.chat.type.in_({"group", "supergroup"}))
    async def upsert_participants(message: Message) -> None:
        if not message.from_user:
            return
        await ctx.roles.upsert_chat(message.chat.id, message.chat.title or "Объект")
        await ctx.roles.upsert_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )

    return router
