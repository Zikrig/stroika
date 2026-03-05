# pyright: reportUnusedFunction=false
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import mark_purchased, mark_shipped, return_to_pdo, take_request
from app.bot.keyboards.menus import cancel_inline, private_main_menu_inline
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._helpers import private_fsm
from app.bot.routers._publish import (
    get_request_actions_keyboard_group,
    safe_update_request_in_group,
)
from app.bot.states import ActionInputStates
from app.config import get_settings
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="procurement")
    admin_ids = set(get_settings().admin_id_list)

    async def _role(user_id: int) -> Role | None:
        return await ctx.roles.get_global_role(user_id)

    async def _menu(uid: int):
        role = await _role(uid)
        return private_main_menu_inline(role=role, is_admin=uid in admin_ids)

    # ── Take (one-click) ─────────────────────────────────────────────

    @router.callback_query(F.data.startswith("take_proc:"))
    async def take_proc(call: CallbackQuery) -> None:
        role = await _role(call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await take_request.take_by_procurement(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=group_chat_id,
                source_message_id=call.message.message_id,
                reply_markup=await get_request_actions_keyboard_group(ctx, req),
            )
            if err:
                await call.answer(err, show_alert=True)
                return
        await call.answer("Заявка взята в работу")

    # ── Purchased (group → DM FSM) ───────────────────────────────────

    @router.callback_query(F.data.startswith("purchased:"))
    async def purchased_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_purchase_date)
        await p_state.update_data(target_request_id=request_id, target_chat_id=group_chat_id, source_message_id=call.message.message_id)
        try:
            await call.bot.send_message(call.from_user.id, "Укажите ожидаемую дату отгрузки", reply_markup=cancel_inline())
        except Exception:
            await call.answer("Сначала напишите /start боту в личку", show_alert=True)
            await p_state.clear()
            return
        await call.answer("Продолжите в личных сообщениях")

    @router.message(ActionInputStates.waiting_purchase_date, F.chat.type == "private")
    async def purchased_date(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        target_chat_id = data["target_chat_id"]
        try:
            req = await mark_purchased.execute(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if req:
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=target_chat_id,
                reply_markup=await get_request_actions_keyboard_group(ctx, req),
            )
            if err:
                await message.answer(err, reply_markup=await _menu(message.from_user.id))
                return
        await message.answer("Этап 'Закуплено' сохранен", reply_markup=await _menu(message.from_user.id))

    # ── Shipped (group → DM FSM) ─────────────────────────────────────

    @router.callback_query(F.data.startswith("shipped:"))
    async def shipped_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_ship_date)
        await p_state.update_data(target_request_id=request_id, target_chat_id=group_chat_id, source_message_id=call.message.message_id)
        try:
            await call.bot.send_message(call.from_user.id, "Укажите ожидаемую дату поставки на объект", reply_markup=cancel_inline())
        except Exception:
            await call.answer("Сначала напишите /start боту в личку", show_alert=True)
            await p_state.clear()
            return
        await call.answer("Продолжите в личных сообщениях")

    @router.message(ActionInputStates.waiting_ship_date, F.chat.type == "private")
    async def shipped_date(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        target_chat_id = data["target_chat_id"]
        try:
            req = await mark_shipped.execute(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if req:
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=target_chat_id,
                reply_markup=await get_request_actions_keyboard_group(ctx, req),
            )
            if err:
                await message.answer(err, reply_markup=await _menu(message.from_user.id))
                return
        await message.answer("Этап 'Отгружено' сохранен", reply_markup=await _menu(message.from_user.id))

    # ── Return to PDO (one-click) ────────────────────────────────────

    @router.callback_query(F.data.startswith("return_pdo:"))
    async def return_to_pdo_click(call: CallbackQuery) -> None:
        role = await _role(call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await return_to_pdo.execute(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=group_chat_id,
                reply_markup=await get_request_actions_keyboard_group(ctx, req),
            )
            if err:
                await call.answer(err, show_alert=True)
                return
        await call.answer("Возвращено в ПДО")

    return router
