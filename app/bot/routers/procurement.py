from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import mark_purchased, mark_shipped, return_to_pdo, take_request
from app.bot.keyboards.menus import cancel_inline
from app.bot.routers._guards import is_latest_request_message
from app.bot.keyboards.request_actions import request_actions_keyboard
from app.bot.routers._publish import publish_request_event
from app.bot.states import ActionInputStates
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="procurement")

    async def _role(chat_id: int, user_id: int) -> Role | None:
        return await ctx.roles.get_role(chat_id, user_id)

    @router.callback_query(F.data.startswith("take_proc:"))
    async def take_proc(call: CallbackQuery) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await take_request.take_by_procurement(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=call.message.chat.id,
                request=req,
                reply_markup=request_actions_keyboard(req, role),
            )
        await call.answer("Заявка взята в работу")

    @router.callback_query(F.data.startswith("purchased:"))
    async def purchased_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_purchase_date)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.message.answer("Укажите ожидаемую дату отгрузки", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ActionInputStates.waiting_purchase_date)
    async def purchased_date(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, data["target_request_id"], message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        try:
            req = await mark_purchased.execute(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if req:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=message.chat.id,
                request=req,
                reply_markup=request_actions_keyboard(req, Role.PROCUREMENT),
            )
        await message.answer("Этап 'Закуплено' сохранен")

    @router.callback_query(F.data.startswith("shipped:"))
    async def shipped_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_ship_date)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.message.answer("Укажите ожидаемую дату поставки на объект", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ActionInputStates.waiting_ship_date)
    async def shipped_date(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, data["target_request_id"], message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        try:
            req = await mark_shipped.execute(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if req:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=message.chat.id,
                request=req,
                reply_markup=request_actions_keyboard(req, Role.FOREMAN),
            )
        await message.answer("Этап 'Отгружено' сохранен")

    @router.callback_query(F.data.startswith("return_pdo:"))
    async def return_to_pdo(call: CallbackQuery) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.PROCUREMENT:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await return_to_pdo.execute(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=call.message.chat.id,
                request=req,
                reply_markup=request_actions_keyboard(req, Role.PDO),
            )
        await call.answer("Возвращено в ПДО")

    return router
