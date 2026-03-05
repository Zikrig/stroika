# pyright: reportUnusedFunction=false
import logging

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
    get_request_actions_keyboard_group,
    safe_update_request_in_group,
)
from app.bot.states import ActionInputStates
from app.config import get_settings
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher

logger = logging.getLogger("bot.debug")


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

    async def _process_dm_action(
        message: Message,
        state: FSMContext,
        *,
        execute_action,
        note_label: str,
        use_keyboard: bool = True,
    ) -> None:
        """Общий обработчик действий руководителя в ЛС (комментарий, пауза, снятие паузы, прекращение)."""
        data = await state.get_data()
        target_chat_id = data.get("target_chat_id")
        source_message_id = data.get("source_message_id")
        prompt_message_id = data.get("prompt_message_id")
        request_id = data.get("target_request_id")
        text = message.text or ""

        # Если по каким-то причинам состояние потерялось или нет id заявки —
        # не молчим, а даём понятную ошибку.
        if not target_chat_id or not request_id:
            await state.clear()
            if prompt_message_id is not None:
                try:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=prompt_message_id,
                        text="Не удалось определить заявку, начните действие из карточки в группе заново.",
                        reply_markup=None,
                    )
                except Exception:
                    pass
            await message.answer(
                "Не удалось определить заявку, начните действие из карточки в группе заново.",
                reply_markup=await _menu(message.from_user.id),
            )
            return

        req: dict | None = None
        error: str | None = None

        try:
            try:
                # Доменноe действие (запись события, смена статуса и т.п.).
                req = await execute_action(request_id, text)
            except ValueError as exc:
                # Бизнес-ошибка — возвращаем текст как есть и не трогаем состояние:
                # пользователь может скорректировать ввод.
                await message.answer(str(exc))
                return
            await state.clear()

            if req:
                reply_markup = await get_request_actions_keyboard_group(ctx, req) if use_keyboard else None
                err = await safe_update_request_in_group(
                    ctx=ctx,
                    publisher=publisher,
                    request=req,
                    target_chat_id=target_chat_id,
                    source_message_id=source_message_id,
                    reply_markup=reply_markup,
                    note=text,
                    note_label=note_label,
                )
                if err:
                    error = err
        except Exception as e:
            logger.exception("%s: не удалось выполнить действие (request_id=%s): %s", note_label, request_id, e)
            error = "Не удалось выполнить действие, попробуйте ещё раз."

        # В любом случае стараемся закрыть диалоговое сообщение в личке.
        if prompt_message_id is not None:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=prompt_message_id,
                    text="Принято",
                    reply_markup=None,
                )
            except Exception:
                pass

        # Сообщение пользователю — всегда что‑то отправляем.
        if error:
            await message.answer(error, reply_markup=await _menu(message.from_user.id))
        else:
            await message.answer("Принято", reply_markup=await _menu(message.from_user.id))

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
        async def _exec(request_id: str, text: str):
            return await manager_actions.comment(ctx.requests, request_id, message.from_user.id, text)

        await _process_dm_action(
            message,
            state,
            execute_action=_exec,
            note_label="Комментарий руководителя",
        )

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
        async def _exec(request_id: str, text: str):
            return await pause_resume_request.pause(ctx.requests, request_id, message.from_user.id, text)

        await _process_dm_action(
            message,
            state,
            execute_action=_exec,
            note_label="Причина паузы",
        )

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
        async def _exec(request_id: str, text: str):
            return await pause_resume_request.resume(ctx.requests, request_id, message.from_user.id, text)

        await _process_dm_action(
            message,
            state,
            execute_action=_exec,
            note_label="Комментарий к снятию паузы",
        )

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
        async def _exec(request_id: str, text: str):
            return await manager_actions.terminate(ctx.requests, request_id, message.from_user.id, text)

        await _process_dm_action(
            message,
            state,
            execute_action=_exec,
            note_label="Причина прекращения",
            use_keyboard=False,
        )

    return router
