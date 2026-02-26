from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import manager_actions, pause_resume_request
from app.bot.keyboards.menus import cancel_inline
from app.bot.keyboards.request_actions import request_actions_keyboard
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._publish import publish_request_event
from app.bot.states import ActionInputStates
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="manager")

    async def _role(chat_id: int, user_id: int) -> Role | None:
        return await ctx.roles.get_role(chat_id, user_id)

    @router.callback_query(F.data.startswith("mgr_comment:"))
    async def comment_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_manager_comment)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.message.answer("Введите комментарий руководителя", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ActionInputStates.waiting_manager_comment)
    async def comment_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, data["target_request_id"], message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        req = await manager_actions.comment(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        await state.clear()
        if req:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=message.chat.id,
                request=req,
                reply_markup=request_actions_keyboard(req, Role.MANAGER),
                note=message.text or "",
                note_label="Комментарий руководителя",
            )

    @router.callback_query(F.data.startswith("pause:"))
    async def pause_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_pause_reason)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.message.answer("Укажите причину паузы", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ActionInputStates.waiting_pause_reason)
    async def pause_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, data["target_request_id"], message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        try:
            req = await pause_resume_request.pause(
                ctx.requests, data["target_request_id"], message.from_user.id, message.text or ""
            )
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
                reply_markup=request_actions_keyboard(req, Role.MANAGER),
                note=message.text or "",
                note_label="Причина паузы",
            )

    @router.callback_query(F.data.startswith("resume:"))
    async def resume_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_resume_comment)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.message.answer("Комментарий к снятию паузы", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ActionInputStates.waiting_resume_comment)
    async def resume_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, data["target_request_id"], message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        try:
            req = await pause_resume_request.resume(
                ctx.requests, data["target_request_id"], message.from_user.id, message.text or ""
            )
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
                reply_markup=request_actions_keyboard(req, Role.MANAGER),
                note=message.text or "",
                note_label="Комментарий к снятию паузы",
            )

    @router.callback_query(F.data.startswith("terminate:"))
    async def terminate_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_terminate_reason)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.message.answer("Укажите причину прекращения", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ActionInputStates.waiting_terminate_reason)
    async def terminate_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, data["target_request_id"], message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        req = await manager_actions.terminate(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        await state.clear()
        if req:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=message.chat.id,
                request=req,
                reply_markup=None,
                note=message.text or "",
                note_label="Причина прекращения",
            )

    return router
