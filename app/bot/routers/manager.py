# pyright: reportUnusedFunction=false
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import manager_actions, pause_resume_request
from app.bot.keyboards.menus import cancel_inline, private_main_menu_inline
from app.bot.keyboards.request_actions import _format_request_label
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._helpers import private_fsm
from app.bot.routers._publish import (
    edit_request_message,
    get_request_actions_keyboard_group,
    publish_event_reply,
    publish_request_event,
)
from app.bot.states import ActionInputStates
from app.config import get_settings
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="manager")
    admin_ids = set(get_settings().admin_id_list)

    async def _role(user_id: int) -> Role | None:
        return await ctx.roles.get_global_role(user_id)

    async def _menu(uid: int):
        role = await _role(uid)
        return private_main_menu_inline(role=role, is_admin=uid in admin_ids)

    # ── helper: redirect FSM to DM ───────────────────────────────────

    async def _redirect_to_dm(call: CallbackQuery, state: FSMContext, fsm_state, prompt: str, request_id: str):
        group_chat_id = call.message.chat.id
        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(fsm_state)
        await p_state.update_data(
            target_request_id=request_id,
            target_chat_id=group_chat_id,
            source_message_id=call.message.message_id,
        )
        try:
            req = await ctx.requests.get_request(request_id)
            label = _format_request_label(req) if req else request_id
            full_prompt = f"{prompt}\n\nЗаявка {label}"
            msg = await call.bot.send_message(call.from_user.id, full_prompt, reply_markup=cancel_inline())
            await p_state.update_data(prompt_message_id=msg.message_id)
        except Exception:
            await call.answer("Сначала напишите /start боту в личку", show_alert=True)
            await p_state.clear()
            return False
        await call.answer("Продолжите в личных сообщениях")
        return True

    # ── Comment ───────────────────────────────────────────────────────

    @router.callback_query(F.data.startswith("mgr_comment:"))
    async def comment_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await _redirect_to_dm(call, state, ActionInputStates.waiting_manager_comment, "Введите комментарий руководителя", request_id)

    @router.message(ActionInputStates.waiting_manager_comment, F.chat.type == "private")
    async def comment_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        target_chat_id = data["target_chat_id"]
        source_message_id = data.get("source_message_id")
        prompt_message_id = data.get("prompt_message_id")
        req = await manager_actions.comment(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        await state.clear()
        if req and source_message_id is not None:
            await edit_request_message(
                ctx=ctx, publisher=publisher,
                chat_id=target_chat_id, message_id=source_message_id,
                request=req, reply_markup=await get_request_actions_keyboard_group(ctx, req),
                note=message.text or "", note_label="Комментарий руководителя",
            )
            events = await ctx.requests.get_events(req["id"])
            if events:
                info = await ctx.requests.get_latest_message_info(req["id"], target_chat_id)
                ct = (info["content_type"] if info else "text")
                await ctx.requests.add_message_link(
                    req["id"], events[-1]["id"], target_chat_id, source_message_id, content_type=ct,
                )
            await publish_event_reply(
                ctx=ctx,
                publisher=publisher,
                chat_id=target_chat_id,
                request_id=req["id"],
                root_message_id=source_message_id,
                note=message.text or "",
                note_label="Комментарий руководителя",
            )
        elif req:
            await publish_request_event(
                ctx=ctx, publisher=publisher, chat_id=target_chat_id,
                request=req, reply_markup=await get_request_actions_keyboard_group(ctx, req),
                note=message.text or "", note_label="Комментарий руководителя",
            )
        if prompt_message_id is not None:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prompt_message_id,
                text="Принято",
                reply_markup=None,
            )
        await message.answer("Принято", reply_markup=await _menu(message.from_user.id))

    # ── Pause ─────────────────────────────────────────────────────────

    @router.callback_query(F.data.startswith("pause:"))
    async def pause_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await _redirect_to_dm(call, state, ActionInputStates.waiting_pause_reason, "Укажите причину паузы", request_id)

    @router.message(ActionInputStates.waiting_pause_reason, F.chat.type == "private")
    async def pause_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        target_chat_id = data["target_chat_id"]
        source_message_id = data.get("source_message_id")
        prompt_message_id = data.get("prompt_message_id")
        try:
            req = await pause_resume_request.pause(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if req and source_message_id is not None:
            await edit_request_message(
                ctx=ctx, publisher=publisher,
                chat_id=target_chat_id, message_id=source_message_id,
                request=req, reply_markup=await get_request_actions_keyboard_group(ctx, req),
                note=message.text or "", note_label="Причина паузы",
            )
            events = await ctx.requests.get_events(req["id"])
            if events:
                info = await ctx.requests.get_latest_message_info(req["id"], target_chat_id)
                ct = (info["content_type"] if info else "text")
                await ctx.requests.add_message_link(
                    req["id"], events[-1]["id"], target_chat_id, source_message_id, content_type=ct,
                )
            await publish_event_reply(
                ctx=ctx,
                publisher=publisher,
                chat_id=target_chat_id,
                request_id=req["id"],
                root_message_id=source_message_id,
                note=message.text or "",
                note_label="Причина паузы",
            )
        elif req:
            await publish_request_event(
                ctx=ctx, publisher=publisher, chat_id=target_chat_id,
                request=req, reply_markup=await get_request_actions_keyboard_group(ctx, req),
                note=message.text or "", note_label="Причина паузы",
            )
        if prompt_message_id is not None:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prompt_message_id,
                text="Принято",
                reply_markup=None,
            )
        await message.answer("Принято", reply_markup=await _menu(message.from_user.id))

    # ── Resume ────────────────────────────────────────────────────────

    @router.callback_query(F.data.startswith("resume:"))
    async def resume_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await _redirect_to_dm(call, state, ActionInputStates.waiting_resume_comment, "Комментарий к снятию паузы", request_id)

    @router.message(ActionInputStates.waiting_resume_comment, F.chat.type == "private")
    async def resume_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        target_chat_id = data["target_chat_id"]
        source_message_id = data.get("source_message_id")
        prompt_message_id = data.get("prompt_message_id")
        try:
            req = await pause_resume_request.resume(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if req and source_message_id is not None:
            await edit_request_message(
                ctx=ctx, publisher=publisher,
                chat_id=target_chat_id, message_id=source_message_id,
                request=req, reply_markup=await get_request_actions_keyboard_group(ctx, req),
                note=message.text or "", note_label="Комментарий к снятию паузы",
            )
            events = await ctx.requests.get_events(req["id"])
            if events:
                info = await ctx.requests.get_latest_message_info(req["id"], target_chat_id)
                ct = (info["content_type"] if info else "text")
                await ctx.requests.add_message_link(
                    req["id"], events[-1]["id"], target_chat_id, source_message_id, content_type=ct,
                )
            await publish_event_reply(
                ctx=ctx,
                publisher=publisher,
                chat_id=target_chat_id,
                request_id=req["id"],
                root_message_id=source_message_id,
                note=message.text or "",
                note_label="Комментарий к снятию паузы",
            )
        elif req:
            await publish_request_event(
                ctx=ctx, publisher=publisher, chat_id=target_chat_id,
                request=req, reply_markup=await get_request_actions_keyboard_group(ctx, req),
                note=message.text or "", note_label="Комментарий к снятию паузы",
            )
        if prompt_message_id is not None:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prompt_message_id,
                text="Принято",
                reply_markup=None,
            )
        await message.answer("Принято", reply_markup=await _menu(message.from_user.id))

    # ── Terminate ─────────────────────────────────────────────────────

    @router.callback_query(F.data.startswith("terminate:"))
    async def terminate_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.MANAGER:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await _redirect_to_dm(call, state, ActionInputStates.waiting_terminate_reason, "Укажите причину прекращения", request_id)

    @router.message(ActionInputStates.waiting_terminate_reason, F.chat.type == "private")
    async def terminate_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        target_chat_id = data["target_chat_id"]
        source_message_id = data.get("source_message_id")
        prompt_message_id = data.get("prompt_message_id")
        req = await manager_actions.terminate(ctx.requests, data["target_request_id"], message.from_user.id, message.text or "")
        await state.clear()
        if req and source_message_id is not None:
            await edit_request_message(
                ctx=ctx, publisher=publisher,
                chat_id=target_chat_id, message_id=source_message_id,
                request=req, reply_markup=None,
                note=message.text or "", note_label="Причина прекращения",
            )
            events = await ctx.requests.get_events(req["id"])
            if events:
                info = await ctx.requests.get_latest_message_info(req["id"], target_chat_id)
                ct = (info["content_type"] if info else "text")
                await ctx.requests.add_message_link(
                    req["id"], events[-1]["id"], target_chat_id, source_message_id, content_type=ct,
                )
            await publish_event_reply(
                ctx=ctx,
                publisher=publisher,
                chat_id=target_chat_id,
                request_id=req["id"],
                root_message_id=source_message_id,
                note=message.text or "",
                note_label="Причина прекращения",
            )
        elif req:
            await publish_request_event(
                ctx=ctx, publisher=publisher, chat_id=target_chat_id,
                request=req, reply_markup=None,
                note=message.text or "", note_label="Причина прекращения",
            )
        if prompt_message_id is not None:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=prompt_message_id,
                text="Принято",
                reply_markup=None,
            )
        await message.answer("Принято", reply_markup=await _menu(message.from_user.id))

    return router
