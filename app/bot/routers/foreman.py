# pyright: reportUnusedFunction=false
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.dto import CreateRequestInput
from app.application.use_cases import confirm_full_received, confirm_partial_received, create_request
from app.application.context import AppContext
from app.bot.keyboards.menus import (
    cancel_inline,
    new_request_description_inline,
    object_picker_inline,
    private_main_menu_inline,
)
from app.bot.keyboards.request_actions import request_actions_keyboard
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._helpers import private_fsm
from app.bot.routers._publish import publish_request_event
from app.bot.states import ActionInputStates, ForemanCreateStates, GroupMenuStates
from app.config import get_settings
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher

_log = logging.getLogger("bot.foreman")


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="foreman")
    admin_ids = set(get_settings().admin_id_list)

    def _is_admin(uid: int) -> bool:
        return uid in admin_ids

    def _menu(uid: int):
        return private_main_menu_inline(is_admin=_is_admin(uid))

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
        chats = await ctx.roles.list_chats()
        if not chats:
            await call.message.answer("Нет зарегистрированных объектов. Админ должен добавить группу командой /add.")
            await call.answer()
            return
        if len(chats) == 1:
            await state.set_state(ForemanCreateStates.waiting_description)
            await state.update_data(
                target_chat_id=chats[0]["id"],
                object_name=chats[0]["title"],
                description_parts=[],
                attachments=[],
            )
            await call.message.answer(
                f"Объект: {chats[0]['title']}\n\n"
                "Шаг 1/4. Отправьте описание потребности.\n"
                "Можно прислать текст, фото, голосовое или файл.",
                reply_markup=new_request_description_inline(),
            )
            await call.answer()
            return
        await state.set_state(ForemanCreateStates.waiting_object_selection)
        await call.message.answer(
            "Выберите объект:",
            reply_markup=object_picker_inline(chats, "pick_obj_new"),
        )
        await call.answer()

    @router.callback_query(
        ForemanCreateStates.waiting_object_selection,
        F.data.startswith("pick_obj_new:"),
    )
    async def pick_object_for_new(call: CallbackQuery, state: FSMContext) -> None:
        chat_id = int(call.data.split(":", maxsplit=1)[1])
        chats = await ctx.roles.list_chats()
        obj = next((c for c in chats if c["id"] == chat_id), None)
        title = obj["title"] if obj else "Объект"
        await state.set_state(ForemanCreateStates.waiting_description)
        await state.update_data(
            target_chat_id=chat_id,
            object_name=title,
            description_parts=[],
            attachments=[],
        )
        await call.message.answer(
            f"Объект: {title}\n\n"
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
        await publish_request_event(
            ctx=ctx,
            publisher=publisher,
            chat_id=target_chat_id,
            request=req,
            reply_markup=request_actions_keyboard(req, role or Role.FOREMAN),
        )
        await message.answer(
            f"Заявка создана: {req['request_code']}",
            reply_markup=_menu(message.from_user.id),
        )

    # ── Lists (active / archive / search / history) ───────────────────

    @router.callback_query(F.data == "pm:active")
    async def list_active(call: CallbackQuery, state: FSMContext) -> None:
        chats = await ctx.roles.list_chats()
        if not chats:
            await call.message.answer("Нет объектов.", reply_markup=_menu(call.from_user.id))
            await call.answer()
            return
        if len(chats) == 1:
            await _show_active(call.message, chats[0]["id"], call.from_user.id)
            await call.answer()
            return
        await state.set_state(GroupMenuStates.waiting_object_for_active)
        await call.message.answer(
            "Выберите объект:",
            reply_markup=object_picker_inline(chats, "pick_obj_active"),
        )
        await call.answer()

    @router.callback_query(
        GroupMenuStates.waiting_object_for_active,
        F.data.startswith("pick_obj_active:"),
    )
    async def pick_obj_active(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        chat_id = int(call.data.split(":", maxsplit=1)[1])
        await _show_active(call.message, chat_id, call.from_user.id)
        await call.answer()

    async def _show_active(message: Message, chat_id: int, user_id: int) -> None:
        items = await ctx.requests.list_requests(chat_id, archived=False)
        if not items:
            await message.answer("Активных заявок нет", reply_markup=_menu(user_id))
            return
        lines = [f"{i['request_code']} | {i.get('name_from_foreman') or '-'} | {i['stage_code']}" for i in items]
        await message.answer("\n".join(lines), reply_markup=_menu(user_id))

    @router.callback_query(F.data == "pm:archive")
    async def list_archive(call: CallbackQuery, state: FSMContext) -> None:
        chats = await ctx.roles.list_chats()
        if not chats:
            await call.message.answer("Нет объектов.", reply_markup=_menu(call.from_user.id))
            await call.answer()
            return
        if len(chats) == 1:
            await _show_archive(call.message, chats[0]["id"], call.from_user.id)
            await call.answer()
            return
        await state.set_state(GroupMenuStates.waiting_object_for_archive)
        await call.message.answer(
            "Выберите объект:",
            reply_markup=object_picker_inline(chats, "pick_obj_archive"),
        )
        await call.answer()

    @router.callback_query(
        GroupMenuStates.waiting_object_for_archive,
        F.data.startswith("pick_obj_archive:"),
    )
    async def pick_obj_archive(call: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        chat_id = int(call.data.split(":", maxsplit=1)[1])
        await _show_archive(call.message, chat_id, call.from_user.id)
        await call.answer()

    async def _show_archive(message: Message, chat_id: int, user_id: int) -> None:
        items = await ctx.requests.list_requests(chat_id, archived=True)
        if not items:
            await message.answer("Архив пуст", reply_markup=_menu(user_id))
            return
        lines = [f"{i['request_code']} | {i['status_code']}" for i in items]
        await message.answer("\n".join(lines), reply_markup=_menu(user_id))

    @router.callback_query(F.data == "pm:search")
    async def search_button(call: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(GroupMenuStates.waiting_search_query)
        await call.message.answer("Введите слово для поиска", reply_markup=cancel_inline())
        await call.answer()

    @router.message(GroupMenuStates.waiting_search_query, F.chat.type == "private")
    async def search_input(message: Message, state: FSMContext) -> None:
        query = (message.text or "").strip()
        await state.clear()
        chats = await ctx.roles.list_chats()
        all_items: list[str] = []
        for chat in chats:
            items = await ctx.requests.list_requests(chat["id"], archived=False, search=query)
            for i in items:
                all_items.append(f"{i['request_code']} | {i.get('nomenclature_1c') or i.get('name_from_foreman') or '-'}")
        if not all_items:
            await message.answer("Ничего не найдено", reply_markup=_menu(message.from_user.id))
            return
        await message.answer("\n".join(all_items), reply_markup=_menu(message.from_user.id))

    @router.callback_query(F.data == "pm:history")
    async def history_button(call: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(GroupMenuStates.waiting_history_code)
        await call.message.answer("Введите ID заявки, например IG-24", reply_markup=cancel_inline())
        await call.answer()

    @router.message(GroupMenuStates.waiting_history_code, F.chat.type == "private")
    async def history_input(message: Message, state: FSMContext) -> None:
        code = (message.text or "").strip()
        await state.clear()
        chats = await ctx.roles.list_chats()
        for chat in chats:
            request = await ctx.requests.get_request_by_code(chat["id"], code)
            if request:
                events = await ctx.requests.get_events_with_attachment_counts(request["id"])
                if not events:
                    await message.answer("История пока пустая", reply_markup=_menu(message.from_user.id))
                    return
                lines = [f"История {code}:"]
                for e in events:
                    created = str(e.get("created_at") or "-")
                    lines.append(f"- {created} | {e['event_type']} | вложений: {e.get('attachments_count', 0)}")
                await message.answer("\n".join(lines), reply_markup=_menu(message.from_user.id))
                return
        await message.answer("Заявка не найдена", reply_markup=_menu(message.from_user.id))

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
            await message.answer("Заявка не найдена", reply_markup=_menu(message.from_user.id))
            return
        role = await _role(message.from_user.id)
        await publish_request_event(
            ctx=ctx, publisher=publisher, chat_id=target_chat_id,
            request=req, reply_markup=request_actions_keyboard(req, role or Role.FOREMAN),
        )
        await message.answer("Получение (частично) зафиксировано", reply_markup=_menu(message.from_user.id))

    @router.callback_query(F.data.startswith("received_full:"))
    async def received_full_click(call: CallbackQuery) -> None:
        role = await _role(call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await confirm_full_received.execute(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            await publish_request_event(
                ctx=ctx, publisher=publisher, chat_id=group_chat_id, request=req, reply_markup=None,
            )
        await call.answer("Заявка закрыта")

    return router
