# pyright: reportUnusedFunction=false
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.dto import CreateRequestInput
from app.application.use_cases import confirm_full_received, confirm_partial_received, create_request
from app.application.context import AppContext
from app.bot.keyboards.menus import (
    PAGE_SIZE,
    cancel_inline,
    new_request_description_inline,
    private_main_menu_inline,
    request_list_inline,
    request_view_inline,
)
from app.bot.formatters.request_card import _fmt_date
from app.bot.routers._publish import (
    get_request_actions_keyboard_group,
    publish_request_event,
    safe_update_request_in_group,
)
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._helpers import private_fsm
from app.bot.states import ActionInputStates, ForemanCreateStates, ForemanEditStates, GroupMenuStates
from app.config import get_settings
from app.domain.enums import EventType, Role, StageCode
from app.infrastructure.telegram.publisher import TelegramPublisher

_log = logging.getLogger("bot.foreman")


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="foreman")
    admin_ids = set(get_settings().admin_id_list)

    def _is_admin(uid: int) -> bool:
        return uid in admin_ids

    async def _menu(uid: int):
        role = await _role(uid)
        return private_main_menu_inline(role=role, is_admin=_is_admin(uid))

    async def _role(user_id: int) -> Role | None:
        return await ctx.roles.get_global_role(user_id)

    def _extract_attachments(message: Message) -> list[dict]:
        attachments: list[dict] = []
        for attr, atype in [
            ("photo", "photo"), ("document", "document"), ("voice", "voice"),
            ("video", "video"), ("audio", "audio"), ("video_note", "video_note"),
        ]:
            obj = getattr(message, attr, None)
            if obj is None:
                continue
            if attr == "photo":
                obj = message.photo[-1]
            attachments.append({
                "file_id": obj.file_id,
                "file_unique_id": obj.file_unique_id,
                "attachment_type": atype,
            })
        return attachments

    # ── New request (private) ─────────────────────────────────────────

    @router.callback_query(F.data == "pm:new_request")
    async def new_request(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Действие доступно только роли Прораб", show_alert=True)
            return
        await state.set_state(ForemanCreateStates.waiting_description)
        await state.update_data(
            target_chat_id=ctx.group_chat_id,
            object_name=ctx.group_title,
            description_parts=[],
            attachments=[],
        )
        await call.message.answer(
            f"Объект: {ctx.group_title}\n\n"
            "Шаг 1/4. Отправьте описание потребности.\n"
            "Можно прислать текст, фото, голосовое или файл.",
            reply_markup=new_request_description_inline(),
        )
        await call.answer()

    # ── Description step ──────────────────────────────────────────────

    @router.message(ForemanCreateStates.waiting_description, F.chat.type == "private")
    async def create_step_description(message: Message, state: FSMContext) -> None:
        description = (message.text or message.caption or "").strip()
        attachments = _extract_attachments(message)
        if not description and not attachments:
            await message.answer(
                "Отправьте текст или вложение.\nПосле этого нажмите «Далее».",
                reply_markup=new_request_description_inline(),
            )
            return
        data = await state.get_data()
        parts = list(data.get("description_parts", []))
        existing = list(data.get("attachments", []))
        if description:
            parts.append(description)
        existing.extend(attachments)
        await state.update_data(description_parts=parts, attachments=existing)

        if attachments and not description:
            text = "Вложение принято. Что-то еще или переходим к следующему шагу?"
        elif attachments and description:
            text = "Сообщение и вложение приняты. Что-то еще или переходим к следующему шагу?"
        else:
            text = "Текст принят. Что-то еще или переходим к следующему шагу?"
        await message.answer(text, reply_markup=new_request_description_inline())

    @router.callback_query(ForemanCreateStates.waiting_description, F.data == "newreq_add_more")
    async def newreq_add_more(call: CallbackQuery) -> None:
        await call.message.answer(
            "Отправьте еще текст или вложение.\nКогда закончите, нажмите «Далее».",
            reply_markup=new_request_description_inline(),
        )
        await call.answer()

    @router.callback_query(ForemanCreateStates.waiting_description, F.data == "newreq_next")
    async def newreq_next(call: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        if not data.get("description_parts") and not data.get("attachments"):
            await call.answer("Сначала отправьте текст или вложение", show_alert=True)
            return
        await state.update_data(
            description=("\n".join(data.get("description_parts", [])).strip() or "Вложение без текстового описания"),
        )
        await state.set_state(ForemanCreateStates.waiting_qty)
        await call.message.answer("Шаг 2/4. Отправьте количество (или 0).", reply_markup=cancel_inline())
        await call.answer()

    # ── Qty / subobject / need_by steps ───────────────────────────────

    @router.message(ForemanCreateStates.waiting_qty, F.chat.type == "private")
    async def create_step_qty(message: Message, state: FSMContext) -> None:
        try:
            qty = float((message.text or "0").replace(",", "."))
        except Exception:
            await message.answer("Отправьте количество числом. Например: 10 или 0", reply_markup=cancel_inline())
            return
        await state.update_data(qty=qty)
        await state.set_state(ForemanCreateStates.waiting_subobject)
        await message.answer("Шаг 3/4. Отправьте подобъект (или '-').", reply_markup=cancel_inline())

    @router.message(ForemanCreateStates.waiting_subobject, F.chat.type == "private")
    async def create_step_subobject(message: Message, state: FSMContext) -> None:
        sub = (message.text or "").strip()
        await state.update_data(subobject=None if sub in {"", "-"} else sub)
        await state.set_state(ForemanCreateStates.waiting_need_by)
        await message.answer("Шаг 4/4. Отправьте срок потребности (или '-').", reply_markup=cancel_inline())

    @router.message(ForemanCreateStates.waiting_need_by, F.chat.type == "private")
    async def create_step_need_by(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        need_by = (message.text or "").strip()
        target_chat_id = data["target_chat_id"]
        object_name = data.get("object_name", "Объект")
        req = await create_request.execute(
            ctx.requests,
            CreateRequestInput(
                chat_id=target_chat_id,
                foreman_user_id=message.from_user.id,
                object_name=object_name,
                description=data.get("description", ""),
                requested_qty=float(data.get("qty", 0.0)),
                unit="шт",
                subobject_name=data.get("subobject"),
                need_by=None if need_by in {"", "-"} else need_by,
                attachments=data.get("attachments", []),
            ),
        )
        await state.clear()
        role = await _role(message.from_user.id)
        try:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=target_chat_id,
                request=req,
                reply_markup=await get_request_actions_keyboard_group(ctx, req),
            )
        except TelegramBadRequest as e:
            if "chat not found" in (e.message or "").lower():
                _log.warning("Group chat not found for GROUP_CHAT_ID=%s: %s", target_chat_id, e)
                await message.answer(
                    f"Заявка {req['request_code']} создана, но не удалось отправить карточку в группу.\n"
                    "Проверьте GROUP_CHAT_ID в .env и что бот добавлен в группу.",
                    reply_markup=await _menu(message.from_user.id),
                )
                return
            raise
        await message.answer(
            f"Заявка создана: {req['request_code']}",
            reply_markup=await _menu(message.from_user.id),
        )

    # ── Lists (active / archive) — paginated buttons ───────────────────

    _EDITABLE_STAGES = {StageCode.CREATED.value, StageCode.PDO_PROCESSING.value}

    async def _send_request_page(message: Message, user_id: int, archived: bool, page: int) -> None:
        """List for foreman: my requests across all objects."""
        lt = "r" if archived else "a"
        items, total = await ctx.requests.list_requests_by_foreman(
            user_id, archived=archived, limit=PAGE_SIZE, offset=page * PAGE_SIZE,
        )
        if not items:
            label = "Архив пуст" if archived else "Активных заявок нет"
            await message.answer(label, reply_markup=await _menu(user_id))
            return
        await message.answer(
            "Архив заявок:" if archived else "Активные заявки:",
            reply_markup=request_list_inline(items, page, total, lt),
        )

    async def _send_request_page_by_chat(
        message: Message, chat_id: int, user_id: int, archived: bool, page: int,
    ) -> None:
        """List by object (for PDO, procurement, manager, viewer)."""
        lt = "r" if archived else "a"
        items, total = await ctx.requests.list_requests_paginated(
            chat_id, archived=archived, limit=PAGE_SIZE, offset=page * PAGE_SIZE,
        )
        if not items:
            label = "Архив пуст" if archived else "Активных заявок нет"
            await message.answer(label, reply_markup=await _menu(user_id))
            return
        await message.answer(
            "Архив заявок:" if archived else "Активные заявки:",
            reply_markup=request_list_inline(items, page, total, lt, chat_id=chat_id),
        )

    @router.callback_query(F.data == "pm:active")
    async def list_active(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        role = await _role(call.from_user.id)
        if role == Role.FOREMAN:
            await _send_request_page(call.message, call.from_user.id, archived=False, page=0)
            await call.answer()
            return
        await _send_request_page_by_chat(
            call.message, ctx.group_chat_id, call.from_user.id, archived=False, page=0,
        )
        await call.answer()

    @router.callback_query(F.data == "pm:archive")
    async def list_archive(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        role = await _role(call.from_user.id)
        if role == Role.FOREMAN:
            await _send_request_page(call.message, call.from_user.id, archived=True, page=0)
            await call.answer()
            return
        await _send_request_page_by_chat(
            call.message, ctx.group_chat_id, call.from_user.id, archived=True, page=0,
        )
        await call.answer()

    @router.callback_query(F.data.startswith("rlist:"))
    async def paginate_list(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        parts = call.data.split(":")
        lt, page = parts[1], int(parts[2])
        chat_id = int(parts[3]) if len(parts) > 3 else None
        if chat_id is not None:
            await _send_request_page_by_chat(
                call.message, chat_id, call.from_user.id, archived=(lt == "r"), page=page,
            )
        else:
            await _send_request_page(call.message, call.from_user.id, archived=(lt == "r"), page=page)
        await call.answer()

    @router.callback_query(F.data == "back_to_menu")
    async def back_to_menu(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await call.message.answer("Главное меню", reply_markup=await _menu(call.from_user.id))
        await call.answer()

    @router.callback_query(F.data == "noop")
    async def noop(call: CallbackQuery) -> None:
        await call.answer()

    # ── View single request card ──────────────────────────────────────

    async def _show_request_card(
        message: Message, code: str, user_id: int, lt: str, page: int, chat_id: int | None = None,
    ) -> None:
        request = await ctx.requests.get_request_by_code_global(code)
        if not request:
            await message.answer("Заявка не найдена", reply_markup=await _menu(user_id))
            return
        from app.bot.formatters.request_card import render_request_card
        events = await ctx.requests.get_events(request["id"])
        attachments_summary = await ctx.requests.get_attachment_summary(request["id"])
        foreman_info = None
        if request.get("foreman_user_id"):
            foreman_info = await ctx.roles.get_user(request["foreman_user_id"])
        text = render_request_card(
            request, events=events, attachments_summary=attachments_summary, foreman_info=foreman_info,
        )
        can_edit = (
            request.get("foreman_user_id") == user_id
            and request.get("stage_code") in _EDITABLE_STAGES
        )
        await message.answer(
            text, reply_markup=request_view_inline(request, can_edit, lt, page, chat_id=chat_id),
        )

    @router.callback_query(F.data.startswith("vreq:"))
    async def view_request(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        parts = call.data.split(":")
        lt, page, code = parts[1], int(parts[2]), parts[3]
        chat_id = int(parts[4]) if len(parts) > 4 else None
        await _show_request_card(
            call.message, code, call.from_user.id, lt, page, chat_id=chat_id,
        )
        await call.answer()

    # ── С кем согласовано? ФИО (прораб, до передачи в ПДО) ─────────────

    @router.callback_query(F.data.startswith("approved_by:"))
    async def approved_by_start(call: CallbackQuery, state: FSMContext) -> None:
        request_id = call.data.split(":", maxsplit=1)[1]
        role = await _role(call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Действие доступно только прорабу", show_alert=True)
            return
        req = await ctx.requests.get_request(request_id)
        if not req:
            await call.answer("Заявка не найдена", show_alert=True)
            return
        if req.get("foreman_user_id") != call.from_user.id:
            await call.answer("Это не ваша заявка", show_alert=True)
            return
        if req.get("stage_code") != StageCode.CREATED.value:
            await call.answer("Указать согласование можно только до передачи в ПДО", show_alert=True)
            return
        if call.message.chat.type != "private":
            if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
                await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
                return
        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_approved_by_fio)
        await p_state.update_data(target_request_id=request_id)
        try:
            await call.bot.send_message(
                call.from_user.id,
                "Введите ФИО того, с кем согласована заявка:",
                reply_markup=cancel_inline(),
            )
        except Exception:
            await call.answer("Напишите боту /start в личку, чтобы отправить ФИО", show_alert=True)
            await p_state.clear()
            return
        await call.answer()

    @router.message(ActionInputStates.waiting_approved_by_fio, F.chat.type == "private")
    async def approved_by_fio_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        request_id = data.get("target_request_id")
        await state.clear()
        if not request_id:
            await message.answer("Сессия сброшена. Выберите заявку снова.", reply_markup=await _menu(message.from_user.id))
            return
        req = await ctx.requests.get_request(request_id)
        if not req or req.get("foreman_user_id") != message.from_user.id or req.get("stage_code") != StageCode.CREATED.value:
            await message.answer("Заявка не найдена или изменить согласование уже нельзя.", reply_markup=await _menu(message.from_user.id))
            return
        fio = (message.text or message.caption or "").strip() or "-"
        updated = await ctx.requests.update_foreman_fields(request_id, {"approved_by": fio})
        if updated:
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=updated,
                target_chat_id=updated["chat_id"],
                reply_markup=await get_request_actions_keyboard_group(ctx, updated),
            )
            if err:
                await message.answer(err, reply_markup=await _menu(message.from_user.id))
                return
        await message.answer(
            f"С кем согласовано: {fio}\nЗаявка {updated.get('request_code', '')} обновлена.",
            reply_markup=await _menu(message.from_user.id),
        )

    # ── Edit foreman fields ───────────────────────────────────────────

    _EDIT_FIELD_MAP = {
        "d": ("name_from_foreman", ForemanEditStates.waiting_edit_description, "Введите новое описание:"),
        "q": ("requested_qty", ForemanEditStates.waiting_edit_qty, "Введите новое количество:"),
        "s": ("subobject_name", ForemanEditStates.waiting_edit_subobject, "Введите новый подобъект (или '-' для пустого):"),
        "n": ("need_by", ForemanEditStates.waiting_edit_need_by, "Введите новый срок (или '-' для пустого):"),
    }

    @router.callback_query(F.data.startswith("ed:"))
    async def edit_field_start(call: CallbackQuery, state: FSMContext) -> None:
        parts = call.data.split(":")
        field_key, code = parts[1], parts[2]
        if field_key not in _EDIT_FIELD_MAP:
            await call.answer("Неизвестное поле", show_alert=True)
            return
        request = await ctx.requests.get_request_by_code_global(code)
        if not request:
            await call.answer("Заявка не найдена", show_alert=True)
            return
        if request.get("foreman_user_id") != call.from_user.id:
            await call.answer("Это не ваша заявка", show_alert=True)
            return
        if request.get("stage_code") not in _EDITABLE_STAGES:
            await call.answer("Редактирование больше недоступно", show_alert=True)
            return

        db_field, fsm_state, prompt = _EDIT_FIELD_MAP[field_key]
        await state.set_state(fsm_state)
        await state.update_data(edit_request_code=code, edit_db_field=db_field)
        await call.message.answer(prompt, reply_markup=cancel_inline())
        await call.answer()

    async def _finish_edit(message: Message, state: FSMContext, value: object) -> None:
        data = await state.get_data()
        code = data["edit_request_code"]
        db_field = data["edit_db_field"]
        await state.clear()

        request = await ctx.requests.get_request_by_code_global(code)
        if not request or request.get("stage_code") not in _EDITABLE_STAGES:
            await message.answer("Редактирование больше недоступно", reply_markup=await _menu(message.from_user.id))
            return

        updated = await ctx.requests.update_foreman_fields(request["id"], {db_field: value})
        if not updated:
            await message.answer("Ошибка обновления", reply_markup=await _menu(message.from_user.id))
            return

        role = await _role(message.from_user.id)
        err = await safe_update_request_in_group(
            ctx=ctx,
            publisher=publisher,
            request=updated,
            target_chat_id=updated["chat_id"],
            reply_markup=await get_request_actions_keyboard_group(ctx, updated),
        )
        if err:
            await message.answer(err, reply_markup=await _menu(message.from_user.id))
            return
        await message.answer(f"Заявка {code} обновлена", reply_markup=await _menu(message.from_user.id))

    @router.message(ForemanEditStates.waiting_edit_description, F.chat.type == "private")
    async def edit_description_input(message: Message, state: FSMContext) -> None:
        text = (message.text or "").strip()
        if not text:
            await message.answer("Введите непустое описание:")
            return
        await _finish_edit(message, state, text)

    @router.message(ForemanEditStates.waiting_edit_qty, F.chat.type == "private")
    async def edit_qty_input(message: Message, state: FSMContext) -> None:
        try:
            qty = float((message.text or "0").replace(",", "."))
        except (ValueError, TypeError):
            await message.answer("Введите количество числом:")
            return
        await _finish_edit(message, state, qty)

    @router.message(ForemanEditStates.waiting_edit_subobject, F.chat.type == "private")
    async def edit_subobject_input(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        await _finish_edit(message, state, None if raw in {"", "-"} else raw)

    @router.message(ForemanEditStates.waiting_edit_need_by, F.chat.type == "private")
    async def edit_need_by_input(message: Message, state: FSMContext) -> None:
        raw = (message.text or "").strip()
        await _finish_edit(message, state, None if raw in {"", "-"} else raw)

    # ── Search / history ──────────────────────────────────────────────

    @router.callback_query(F.data == "pm:search")
    async def search_button(call: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(GroupMenuStates.waiting_search_query)
        await call.message.answer("Введите слово для поиска", reply_markup=cancel_inline())
        await call.answer()

    @router.message(GroupMenuStates.waiting_search_query, F.chat.type == "private")
    async def search_input(message: Message, state: FSMContext) -> None:
        query = (message.text or "").strip()
        await state.clear()
        items = await ctx.requests.list_requests(ctx.group_chat_id, archived=False, search=query)
        all_items = [
            f"{i['request_code']} | {i.get('nomenclature_1c') or i.get('name_from_foreman') or '-'}"
            for i in items
        ]
        if not all_items:
            await message.answer("Ничего не найдено", reply_markup=await _menu(message.from_user.id))
            return
        await message.answer("\n".join(all_items), reply_markup=await _menu(message.from_user.id))

    @router.callback_query(F.data == "pm:history")
    async def history_button(call: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(GroupMenuStates.waiting_history_code)
        await call.message.answer("Введите ID заявки, например IG-24", reply_markup=cancel_inline())
        await call.answer()

    @router.message(GroupMenuStates.waiting_history_code, F.chat.type == "private")
    async def history_input(message: Message, state: FSMContext) -> None:
        code = (message.text or "").strip()
        await state.clear()
        request = await ctx.requests.get_request_by_code(ctx.group_chat_id, code)
        if request:
            events = await ctx.requests.get_events_with_attachment_counts(request["id"])
            if not events:
                await message.answer("История пока пустая", reply_markup=await _menu(message.from_user.id))
                return
            lines = [f"История {code}:"]
            for e in events:
                created = _fmt_date(e.get("created_at"))
                lines.append(f"- {created} | {e['event_type']} | вложений: {e.get('attachments_count', 0)}")
            await message.answer("\n".join(lines), reply_markup=await _menu(message.from_user.id))
            return
        await message.answer("Заявка не найдена", reply_markup=await _menu(message.from_user.id))

    # ── Received partial / full (group card callbacks → DM) ───────────

    @router.callback_query(F.data.startswith("received_partial:"))
    async def received_partial_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_partial_qty)
        await p_state.update_data(
            target_request_id=request_id,
            target_chat_id=group_chat_id,
            source_message_id=call.message.message_id,
        )
        try:
            await call.bot.send_message(call.from_user.id, "Введите полученное количество (дельта)", reply_markup=cancel_inline())
        except Exception:
            await call.answer("Сначала напишите /start боту в личку", show_alert=True)
            await p_state.clear()
            return
        await call.answer("Продолжите в личных сообщениях")

    @router.message(ActionInputStates.waiting_partial_qty, F.chat.type == "private")
    async def received_partial_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        request_id = data["target_request_id"]
        target_chat_id = data["target_chat_id"]
        delta = float((message.text or "0").replace(",", "."))
        try:
            req = await confirm_partial_received.execute(ctx.requests, request_id, message.from_user.id, delta)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if not req:
            await message.answer("Заявка не найдена", reply_markup=await _menu(message.from_user.id))
            return
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
        await message.answer("Получение (частично) зафиксировано", reply_markup=await _menu(message.from_user.id))

    def _delivery_photo_choice_inline() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Выполните фото", callback_data="delivery_photo_do"),
                    InlineKeyboardButton(text="Пропустить", callback_data="delivery_photo_skip"),
                ],
                [InlineKeyboardButton(text="Отмена", callback_data="cancel_flow")],
            ]
        )

    @router.callback_query(F.data.startswith("received_full:"))
    async def received_full_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_full_received_choice)
        await p_state.update_data(
            target_request_id=request_id,
            target_chat_id=group_chat_id,
        )
        try:
            req = await ctx.requests.get_request(request_id)
            code = req.get("request_code", "") if req else ""
            await call.bot.send_message(
                call.from_user.id,
                f"Заявка {code} получена на объекте. Сфотографируйте поставку или пропустите.",
                reply_markup=_delivery_photo_choice_inline(),
            )
        except Exception:
            await call.answer("Напишите боту /start в личку", show_alert=True)
            await p_state.clear()
            return
        await call.answer("Продолжите в личных сообщениях")

    @router.callback_query(
        ActionInputStates.waiting_full_received_choice,
        F.data == "delivery_photo_skip",
    )
    async def delivery_photo_skip(call: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        request_id = data.get("target_request_id")
        target_chat_id = data.get("target_chat_id")
        await state.clear()
        if not request_id or not target_chat_id:
            await call.message.answer("Сессия сброшена.", reply_markup=await _menu(call.from_user.id))
            await call.answer()
            return
        try:
            req = await confirm_full_received.execute(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.message.answer(str(exc), reply_markup=await _menu(call.from_user.id))
            await call.answer()
            return
        if req:
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=target_chat_id,
                reply_markup=None,
            )
            if err:
                await call.message.answer(err, reply_markup=await _menu(call.from_user.id))
                await call.answer()
                return
        await call.message.answer("Заявка закрыта (без фото)", reply_markup=await _menu(call.from_user.id))
        await call.answer()

    @router.callback_query(
        ActionInputStates.waiting_full_received_choice,
        F.data == "delivery_photo_do",
    )
    async def delivery_photo_do(call: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        request_id = data.get("target_request_id")
        if not request_id:
            await state.clear()
            await call.message.answer("Сессия сброшена.", reply_markup=await _menu(call.from_user.id))
            await call.answer()
            return
        await state.set_state(ActionInputStates.waiting_delivery_photo)
        await call.message.answer(
            "Отправьте одно или несколько фото поставки. После отправки заявка будет закрыта.",
            reply_markup=cancel_inline(),
        )
        await call.answer()

    @router.message(
        ActionInputStates.waiting_delivery_photo,
        F.chat.type == "private",
        F.photo,
    )
    async def delivery_photo_received(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        request_id = data.get("target_request_id")
        target_chat_id = data.get("target_chat_id")
        await state.clear()
        if not request_id or not target_chat_id:
            await message.answer("Сессия сброшена.", reply_markup=await _menu(message.from_user.id))
            return
        try:
            req = await confirm_full_received.execute(ctx.requests, request_id, message.from_user.id)
        except ValueError as exc:
            await message.answer(str(exc), reply_markup=await _menu(message.from_user.id))
            return
        if not req:
            await message.answer("Заявка не найдена", reply_markup=await _menu(message.from_user.id))
            return
        events = await ctx.requests.get_events(request_id)
        last_event = next((e for e in reversed(events or []) if e.get("event_type") == EventType.FULLY_RECEIVED.value), None)
        if last_event and message.photo:
            p = message.photo[-1]
            attachments = [{
                "file_id": p.file_id,
                "file_unique_id": getattr(p, "file_unique_id", ""),
                "attachment_type": "photo",
            }]
            await ctx.requests.add_attachments(request_id, last_event["id"], attachments)
        err = await safe_update_request_in_group(
            ctx=ctx,
            publisher=publisher,
            request=req,
            target_chat_id=target_chat_id,
            reply_markup=None,
        )
        if err:
            await message.answer(err, reply_markup=await _menu(message.from_user.id))
            return
        await message.answer("Заявка закрыта, фото добавлено", reply_markup=await _menu(message.from_user.id))

    @router.message(
        ActionInputStates.waiting_delivery_photo,
        F.chat.type == "private",
    )
    async def delivery_photo_other(message: Message, state: FSMContext) -> None:
        await message.answer("Отправьте фото поставки или нажмите «Отмена».", reply_markup=cancel_inline())

    return router
