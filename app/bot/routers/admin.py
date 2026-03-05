# pyright: reportUnusedFunction=false
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import cancel_request
from app.bot.keyboards.menus import cancel_inline, private_main_menu_inline
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._helpers import private_fsm
from app.bot.routers._publish import get_request_actions_keyboard_group, safe_update_request_in_group
from app.bot.states import ActionInputStates, ForemanCreateStates
from app.config import get_settings
from app.domain.enums import EventType, Role
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="actions")
    admin_ids = set(get_settings().admin_id_list)

    async def _role(user_id: int) -> Role | None:
        return await ctx.roles.get_global_role(user_id)

    async def _menu(uid: int):
        role = await _role(uid)
        return private_main_menu_inline(role=role, is_admin=uid in admin_ids)

    # ── Cancel (group card → DM FSM) ─────────────────────────────────

    @router.callback_query(F.data.startswith("cancel:"))
    async def cancel_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role not in {Role.FOREMAN, Role.PDO, Role.PROCUREMENT}:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_cancel_reason)
        await p_state.update_data(
            target_request_id=request_id,
            actor_role=role.value,
            target_chat_id=group_chat_id,
            source_message_id=call.message.message_id,
        )
        try:
            await call.bot.send_message(call.from_user.id, "Укажите причину отмены", reply_markup=cancel_inline())
        except Exception:
            await call.answer("Сначала напишите /start боту в личку", show_alert=True)
            await p_state.clear()
            return
        await call.answer("Продолжите в личных сообщениях")

    @router.message(ActionInputStates.waiting_cancel_reason, F.chat.type == "private")
    async def cancel_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        target_chat_id = data["target_chat_id"]
        source_message_id = data.get("source_message_id")
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
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=target_chat_id,
                source_message_id=source_message_id,
                reply_markup=None,
                note=message.text or "",
                note_label="Причина отмены",
            )
            if err:
                await message.answer(err, reply_markup=await _menu(message.from_user.id))
                return
        await message.answer("Заявка отменена", reply_markup=await _menu(message.from_user.id))

    # ── Repeat: создание заявки с тем же описанием и вложениями, заново вводятся кол-во, подобъект, срок, с кем согласовано ─

    @router.callback_query(F.data.startswith("repeat:"))
    async def repeat_request(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        is_from_private = call.message.chat.type == "private"
        if not is_from_private:
            group_chat_id = call.message.chat.id
            if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
                await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
                return
        else:
            group_chat_id = None  # set from src below

        src = await ctx.requests.get_request(request_id)
        if not src:
            await call.answer("Заявка не найдена", show_alert=True)
            return

        target_chat_id = src.get("chat_id") or (call.message.chat.id if not is_from_private else None)
        if target_chat_id is None:
            from app.config import get_settings
            target_chat_id = get_settings().group_chat_id

        description = (src.get("name_from_foreman") or "").strip()
        events = await ctx.requests.get_events(request_id)
        first_event_id = None
        if events and events[0].get("event_type") == EventType.REQUEST_CREATED.value:
            first_event_id = events[0]["id"]
        repeat_attachments: list[dict] = []
        if first_event_id:
            for a in await ctx.requests.list_attachments(request_id, first_event_id):
                repeat_attachments.append({
                    "file_id": a["file_id"],
                    "file_unique_id": a.get("file_unique_id"),
                    "attachment_type": a["attachment_type"],
                })

        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ForemanCreateStates.waiting_qty)
        await p_state.update_data(
            target_chat_id=target_chat_id,
            object_name=ctx.group_title or src.get("object_name") or "Объект",
            description=description or "Вложение без текстового описания",
            description_parts=[description] if description else [],
            attachments=repeat_attachments,
        )
        try:
            await call.bot.send_message(
                call.from_user.id,
                "Повтор заявки — описание и вложения сохранены. Укажите количество, подобъект, срок и с кем согласовано.\n\n"
                "Шаг 2/5. Отправьте количество (или 0).",
                reply_markup=cancel_inline(),
            )
        except Exception:
            await call.answer("Напишите боту /start в личку", show_alert=True)
            await p_state.clear()
            return
        await call.answer("Продолжите в личных сообщениях")

    return router
