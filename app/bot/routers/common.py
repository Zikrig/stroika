# pyright: reportUnusedFunction=false
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.context import AppContext
from app.bot.keyboards.menus import (
    private_main_menu_inline,
    role_picker_inline,
)
from app.bot.routers._helpers import private_fsm
from app.bot.states import AdminAddObjectStates, RoleOnboardingStates
from app.config import get_settings
from app.domain.enums import Role
from app.domain.services.role_guard import role_title


def get_router(ctx: AppContext) -> Router:
    router = Router(name="common")
    admin_ids = set(get_settings().admin_id_list)

    def _is_admin(user_id: int) -> bool:
        return user_id in admin_ids

    # ── /start (private) ─────────────────────────────────────────────
    @router.message(Command("start"), F.chat.type == "private")
    async def start_private(message: Message, state: FSMContext) -> None:
        await state.clear()
        role = await ctx.roles.get_global_role(message.from_user.id)
        role_text = "не назначена" if role is None else role_title(role)
        await message.answer(
            f"Бот учёта заявок.\nВаша роль: {role_text}",
            reply_markup=private_main_menu_inline(role=role, is_admin=_is_admin(message.from_user.id)),
        )

    # ── /start (group — minimal) ─────────────────────────────────────
    @router.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
    async def start_group(message: Message) -> None:
        await message.answer("Бот учёта заявок. Взаимодействие — в личных сообщениях с ботом.")

    # ── /admin (private) ──────────────────────────────────────────────
    @router.message(Command("admin"), F.chat.type == "private")
    async def admin_private(message: Message) -> None:
        role = await ctx.roles.get_global_role(message.from_user.id)
        role_text = "не назначена" if role is None else role_title(role)
        await message.answer(
            f"Ваша роль: {role_text}",
            reply_markup=private_main_menu_inline(role=role, is_admin=_is_admin(message.from_user.id)),
        )

    # ── /add (group — register object) ───────────────────────────────
    @router.message(Command("add"), F.chat.type.in_({"group", "supergroup"}))
    async def add_object(message: Message, state: FSMContext) -> None:
        chat_id = message.chat.id
        default_title = message.chat.title or "Объект"
        await ctx.roles.upsert_chat(chat_id, default_title)

        p_state = private_fsm(state, message.bot.id, message.from_user.id)
        await p_state.set_state(AdminAddObjectStates.waiting_object_name)
        await p_state.update_data(target_chat_id=chat_id)

        try:
            await message.bot.send_message(
                message.from_user.id,
                f"Группа зарегистрирована (id: {chat_id}).\n"
                f"Текущее название: {default_title}\n\n"
                "Введите название объекта:",
            )
        except Exception:
            await message.answer(
                "Не удалось написать в личку. "
                "Сначала откройте ЛС с ботом и нажмите /start."
            )
            await p_state.clear()
            return

        await message.answer("Продолжите в личных сообщениях с ботом.")

    # ── object naming (private, after /add) ───────────────────────────
    @router.message(AdminAddObjectStates.waiting_object_name, F.chat.type == "private")
    async def name_object(message: Message, state: FSMContext) -> None:
        name = (message.text or "").strip()
        if not name:
            await message.answer("Введите непустое название объекта:")
            return
        data = await state.get_data()
        chat_id = data["target_chat_id"]
        await ctx.roles.upsert_chat(chat_id, name)
        await state.clear()
        role = await ctx.roles.get_global_role(message.from_user.id)
        await message.answer(
            f"Объект сохранён: «{name}» (группа {chat_id})",
            reply_markup=private_main_menu_inline(role=role, is_admin=_is_admin(message.from_user.id)),
        )

    # ── /set (group — assign role via reply) ──────────────────────────
    @router.message(Command("set"), F.chat.type.in_({"group", "supergroup"}))
    async def set_role_reply(message: Message) -> None:
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.answer("Команда /set должна быть ответом на сообщение пользователя")
            return

        target = message.reply_to_message.from_user
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
        except Exception:
            await message.answer("Не удалось написать вам в личку. Сначала откройте ЛС с ботом и нажмите /start.")

    # ── cancel_flow (universal) ───────────────────────────────────────
    @router.callback_query(F.data == "cancel_flow")
    async def cancel_flow(call: CallbackQuery, state: FSMContext) -> None:
        role = await ctx.roles.get_global_role(call.from_user.id)
        if call.message.chat.type == "private":
            await state.clear()
            await call.message.answer(
                "Действие отменено.",
                reply_markup=private_main_menu_inline(role=role, is_admin=_is_admin(call.from_user.id)),
            )
        else:
            p_state = private_fsm(state, call.bot.id, call.from_user.id)
            await p_state.clear()
            try:
                await call.bot.send_message(
                    call.from_user.id,
                    "Действие отменено.",
                    reply_markup=private_main_menu_inline(role=role, is_admin=_is_admin(call.from_user.id)),
                )
            except Exception:
                pass
        await call.answer()

    # ── admin: set my role ────────────────────────────────────────────
    @router.callback_query(F.data == "admin_menu:set_my_role")
    async def admin_set_my_role(call: CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            await call.answer("Доступ запрещён", show_alert=True)
            return
        await call.message.answer("Выберите новую роль для себя:", reply_markup=role_picker_inline())
        await call.answer()

    @router.callback_query(F.data == "admin_menu:set_help")
    async def set_help(call: CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            await call.answer("Доступ запрещён", show_alert=True)
            return
        role = await ctx.roles.get_global_role(call.from_user.id)
        await call.message.answer(
            "Назначение роли другому пользователю:\n"
            "1) В группе ответьте на сообщение пользователя командой /set\n"
            "2) В личку придёт сообщение с кнопками ролей\n"
            "3) Нажмите нужную роль",
            reply_markup=private_main_menu_inline(role=role, is_admin=True),
        )
        await call.answer()

    # ── admin: set user role / pick own role ──────────────────────────

    async def _after_role_assigned(call: CallbackQuery, state: FSMContext, user_id: int, role: Role) -> None:
        """If foreman role, ask for display name in DM."""
        if role != Role.FOREMAN:
            return
        p_state = private_fsm(state, call.bot.id, call.from_user.id) if call.message.chat.type != "private" else state
        onboard_state = private_fsm(state, call.bot.id, user_id) if user_id != call.from_user.id else p_state
        await onboard_state.set_state(RoleOnboardingStates.waiting_foreman_name)
        await onboard_state.update_data(onboard_user_id=user_id)
        try:
            await call.bot.send_message(
                user_id,
                "Вам назначена роль Прораб.\nВведите ваше имя (как оно будет отображаться в заявках):",
            )
        except Exception:
            pass

    @router.callback_query(F.data.startswith("set_user_role:"))
    async def set_user_role_pick(call: CallbackQuery, state: FSMContext) -> None:
        _, user_id_raw, role_raw = call.data.split(":")
        user_id = int(user_id_raw)
        role = Role(role_raw)
        await ctx.roles.upsert_user(user_id, None, f"user_{user_id}")
        await ctx.roles.set_global_role(user_id, role)
        my_role = await ctx.roles.get_global_role(call.from_user.id)
        await call.message.answer(
            f"Роль назначена: user_id={user_id}, role={role_title(role)}",
            reply_markup=private_main_menu_inline(role=my_role, is_admin=_is_admin(call.from_user.id)),
        )
        await _after_role_assigned(call, state, user_id, role)
        await call.answer("Готово")

    @router.callback_query(F.data.startswith("pick_role:"))
    async def set_my_role_pick(call: CallbackQuery, state: FSMContext) -> None:
        if not _is_admin(call.from_user.id):
            await call.answer("Доступ запрещён", show_alert=True)
            return
        role_raw = call.data.split(":", maxsplit=1)[1]
        role = Role(role_raw)
        await ctx.roles.upsert_user(call.from_user.id, call.from_user.username, call.from_user.full_name)
        await ctx.roles.set_global_role(call.from_user.id, role)
        await call.message.answer(
            f"Ваша роль обновлена: {role_title(role)}",
            reply_markup=private_main_menu_inline(role=role, is_admin=True),
        )
        await _after_role_assigned(call, state, call.from_user.id, role)
        await call.answer("Роль сохранена")

    # ── foreman name onboarding (private) ─────────────────────────────

    @router.message(RoleOnboardingStates.waiting_foreman_name, F.chat.type == "private")
    async def foreman_name_input(message: Message, state: FSMContext) -> None:
        name = (message.text or "").strip()
        if not name:
            await message.answer("Введите ваше имя:")
            return
        await ctx.roles.set_display_name(message.from_user.id, name)
        await state.clear()
        role = await ctx.roles.get_global_role(message.from_user.id)
        await message.answer(
            f"Имя сохранено: {name}",
            reply_markup=private_main_menu_inline(role=role, is_admin=_is_admin(message.from_user.id)),
        )

    return router
