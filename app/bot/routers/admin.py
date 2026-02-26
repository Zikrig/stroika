from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.context import AppContext
from app.application.dto import CreateRequestInput
from app.application.use_cases import cancel_request, create_request
from app.bot.keyboards.menus import cancel_inline
from app.bot.keyboards.request_actions import request_actions_keyboard
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._publish import publish_request_event
from app.bot.states import ActionInputStates
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="actions")

    async def _role(chat_id: int, user_id: int) -> Role | None:
        return await ctx.roles.get_role(chat_id, user_id)

    @router.callback_query(F.data.startswith("cancel:"))
    async def cancel_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role not in {Role.FOREMAN, Role.PDO, Role.PROCUREMENT}:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_cancel_reason)
        await state.update_data(
            target_request_id=request_id,
            actor_role=role.value,
            source_message_id=call.message.message_id,
        )
        await call.message.answer("Укажите причину отмены", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ActionInputStates.waiting_cancel_reason)
    async def cancel_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, data["target_request_id"], message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        role = Role(data["actor_role"])
        try:
            req = await cancel_request.execute(
                requests=ctx.requests,
                request_id=data["target_request_id"],
                actor_user_id=message.from_user.id,
                actor_role=role,
                reason=message.text or "",
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
                reply_markup=None,
                note=message.text or "",
                note_label="Причина отмены",
            )

    @router.callback_query(F.data.startswith("repeat:"))
    async def repeat_request(call: CallbackQuery) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        src = await ctx.requests.get_request(request_id)
        if not src:
            await call.answer("Заявка не найдена", show_alert=True)
            return
        req = await create_request.execute(
            ctx.requests,
            CreateRequestInput(
                chat_id=call.message.chat.id,
                foreman_user_id=call.from_user.id,
                object_name=src["object_name"],
                description=src.get("name_from_foreman") or src.get("nomenclature_1c") or "Повтор",
                requested_qty=float(src.get("requested_qty", 0.0)),
                unit=src.get("unit") or "шт",
                subobject_name=src.get("subobject_name"),
                need_by=src.get("need_by"),
            ),
        )
        await publish_request_event(
            ctx=ctx,
            publisher=publisher,
            chat_id=call.message.chat.id,
            request=req,
            reply_markup=request_actions_keyboard(req, Role.FOREMAN),
        )
        await call.answer("Повторная заявка создана")

    return router
