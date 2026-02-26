from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.dto import CreateRequestInput
from app.application.use_cases import confirm_full_received, confirm_partial_received, create_request
from app.application.context import AppContext
from app.bot.keyboards.menus import cancel_inline, group_main_menu_inline, new_request_description_inline
from app.bot.keyboards.request_actions import request_actions_keyboard
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._publish import publish_request_event
from app.bot.states import ActionInputStates, ForemanCreateStates, GroupMenuStates
from app.domain.enums import Role
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="foreman")

    async def _role(chat_id: int, user_id: int) -> Role | None:
        return await ctx.roles.get_role(chat_id, user_id)

    def _extract_attachments(message: Message) -> list[dict]:
        attachments: list[dict] = []
        if message.photo:
            photo = message.photo[-1]
            attachments.append(
                {
                    "file_id": photo.file_id,
                    "file_unique_id": photo.file_unique_id,
                    "attachment_type": "photo",
                }
            )
        if message.document:
            attachments.append(
                {
                    "file_id": message.document.file_id,
                    "file_unique_id": message.document.file_unique_id,
                    "attachment_type": "document",
                }
            )
        if message.voice:
            attachments.append(
                {
                    "file_id": message.voice.file_id,
                    "file_unique_id": message.voice.file_unique_id,
                    "attachment_type": "voice",
                }
            )
        if message.video:
            attachments.append(
                {
                    "file_id": message.video.file_id,
                    "file_unique_id": message.video.file_unique_id,
                    "attachment_type": "video",
                }
            )
        if message.audio:
            attachments.append(
                {
                    "file_id": message.audio.file_id,
                    "file_unique_id": message.audio.file_unique_id,
                    "attachment_type": "audio",
                }
            )
        if message.video_note:
            attachments.append(
                {
                    "file_id": message.video_note.file_id,
                    "file_unique_id": message.video_note.file_unique_id,
                    "attachment_type": "video_note",
                }
            )
        return attachments

    @router.callback_query(F.data == "group_menu:new")
    async def new_request(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Действие доступно только роли Прораб", show_alert=True)
            return
        await state.set_state(ForemanCreateStates.waiting_description)
        await state.update_data(description_parts=[], attachments=[])
        await call.message.answer(
            "Шаг 1/4. Отправьте описание потребности.\n"
            "Можно прислать текст, фото, голосовое или файл.",
            reply_markup=new_request_description_inline(),
        )
        await call.answer()

    @router.message(ForemanCreateStates.waiting_description)
    async def create_step_description(message: Message, state: FSMContext) -> None:
        description = (message.text or message.caption or "").strip()
        attachments = _extract_attachments(message)
        if not description and not attachments:
            await message.answer(
                "Я вас жду на шаге описания.\n"
                "Отправьте текст или вложение.\n"
                "После этого нажмите «Далее».",
                reply_markup=new_request_description_inline(),
            )
            return
        data = await state.get_data()
        description_parts = list(data.get("description_parts", []))
        existing_attachments = list(data.get("attachments", []))
        if description:
            description_parts.append(description)
        existing_attachments.extend(attachments)
        await state.update_data(description_parts=description_parts, attachments=existing_attachments)

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
            "Отправьте еще текст или вложение.\n"
            "Когда закончите, нажмите «Далее».",
            reply_markup=new_request_description_inline(),
        )
        await call.answer()

    @router.callback_query(ForemanCreateStates.waiting_description, F.data == "newreq_next")
    async def newreq_next(call: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        description_parts = list(data.get("description_parts", []))
        attachments = list(data.get("attachments", []))
        if not description_parts and not attachments:
            await call.answer("Сначала отправьте текст или вложение", show_alert=True)
            return
        await state.update_data(
            description=("\n".join(description_parts).strip() or "Вложение без текстового описания"),
            attachments=attachments,
        )
        await state.set_state(ForemanCreateStates.waiting_qty)
        await call.message.answer("Шаг 2/4. Отправьте количество (или 0).", reply_markup=cancel_inline())
        await call.answer()

    @router.message(ForemanCreateStates.waiting_qty)
    async def create_step_qty(message: Message, state: FSMContext) -> None:
        try:
            qty = float((message.text or "0").replace(",", "."))
        except Exception:
            await message.answer("Отправьте количество числом. Например: 10 или 0", reply_markup=cancel_inline())
            return
        await state.update_data(qty=qty)
        await state.set_state(ForemanCreateStates.waiting_subobject)
        await message.answer("Шаг 3/4. Отправьте подобъект (или '-').", reply_markup=cancel_inline())

    @router.message(ForemanCreateStates.waiting_subobject)
    async def create_step_subobject(message: Message, state: FSMContext) -> None:
        sub = (message.text or "").strip()
        await state.update_data(subobject=None if sub in {"", "-"} else sub)
        await state.set_state(ForemanCreateStates.waiting_need_by)
        await message.answer("Шаг 4/4. Отправьте срок потребности (или '-').", reply_markup=cancel_inline())

    @router.message(ForemanCreateStates.waiting_need_by)
    async def create_step_need_by(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        need_by = (message.text or "").strip()
        req = await create_request.execute(
            ctx.requests,
            CreateRequestInput(
                chat_id=message.chat.id,
                foreman_user_id=message.from_user.id,
                object_name=message.chat.title or "Объект",
                description=data.get("description", ""),
                requested_qty=float(data.get("qty", 0.0)),
                unit="шт",
                subobject_name=data.get("subobject"),
                need_by=None if need_by in {"", "-"} else need_by,
                attachments=data.get("attachments", []),
            ),
        )
        await state.clear()
        role = await _role(message.chat.id, message.from_user.id)
        message_id = await publish_request_event(
            ctx=ctx,
            publisher=publisher,
            chat_id=message.chat.id,
            request=req,
            reply_markup=request_actions_keyboard(req, role or Role.FOREMAN),
        )
        await message.answer(f"Заявка создана: {req['request_code']} (msg {message_id})", reply_markup=group_main_menu_inline())

    async def _send_history(message: Message, code: str) -> None:
        request = await ctx.requests.get_request_by_code(message.chat.id, code)
        if not request:
            await message.answer("Заявка не найдена")
            return
        events = await ctx.requests.get_events_with_attachment_counts(request["id"])
        if not events:
            await message.answer("История пока пустая")
            return
        lines = [f"История {code}:"]
        for event in events:
            created = str(event.get("created_at") or "-")
            lines.append(
                f"- {created} | {event['event_type']} | вложений: {event.get('attachments_count', 0)}"
            )
        await message.answer("\n".join(lines), reply_markup=group_main_menu_inline())

    @router.callback_query(F.data == "group_menu:active")
    async def list_active(call: CallbackQuery) -> None:
        message = call.message
        items = await ctx.requests.list_requests(message.chat.id, archived=False)
        if not items:
            await message.answer("Активных заявок нет", reply_markup=group_main_menu_inline())
            await call.answer()
            return
        lines = [f"{item['request_code']} | {item.get('name_from_foreman') or '-'} | {item['stage_code']}" for item in items]
        await message.answer("\n".join(lines), reply_markup=group_main_menu_inline())
        await call.answer()

    @router.callback_query(F.data == "group_menu:archive")
    async def list_archive(call: CallbackQuery) -> None:
        message = call.message
        items = await ctx.requests.list_requests(message.chat.id, archived=True)
        if not items:
            await message.answer("Архив пуст", reply_markup=group_main_menu_inline())
            await call.answer()
            return
        lines = [f"{item['request_code']} | {item['status_code']}" for item in items]
        await message.answer("\n".join(lines), reply_markup=group_main_menu_inline())
        await call.answer()

    @router.callback_query(F.data == "group_menu:search")
    async def search_button(call: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(GroupMenuStates.waiting_search_query)
        await call.message.answer("Введите слово для поиска", reply_markup=cancel_inline())
        await call.answer()

    @router.message(GroupMenuStates.waiting_search_query)
    async def search_input(message: Message, state: FSMContext) -> None:
        query = (message.text or "").strip()
        await state.clear()
        items = await ctx.requests.list_requests(message.chat.id, archived=False, search=query)
        if not items:
            await message.answer("Ничего не найдено", reply_markup=group_main_menu_inline())
            return
        lines = [f"{item['request_code']} | {item.get('nomenclature_1c') or item.get('name_from_foreman') or '-'}" for item in items]
        await message.answer("\n".join(lines), reply_markup=group_main_menu_inline())

    @router.callback_query(F.data == "group_menu:history")
    async def history_button(call: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(GroupMenuStates.waiting_history_code)
        await call.message.answer("Введите ID заявки, например IG-24", reply_markup=cancel_inline())
        await call.answer()

    @router.message(GroupMenuStates.waiting_history_code)
    async def history_input(message: Message, state: FSMContext) -> None:
        code = (message.text or "").strip()
        await state.clear()
        await _send_history(message, code)

    @router.callback_query(F.data == "group_menu:chat_id")
    async def chat_id_button(call: CallbackQuery) -> None:
        await call.message.answer(f"chat_id этой группы: {call.message.chat.id}", reply_markup=group_main_menu_inline())
        await call.answer()

    @router.callback_query(F.data.startswith("received_partial:"))
    async def received_partial_click(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        await state.set_state(ActionInputStates.waiting_partial_qty)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.message.answer("Введите полученное количество (дельта)")
        await call.answer()

    @router.message(ActionInputStates.waiting_partial_qty)
    async def received_partial_input(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        request_id = data["target_request_id"]
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(ctx, request_id, message.chat.id, source_message_id):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
        delta = float((message.text or "0").replace(",", "."))
        try:
            req = await confirm_partial_received.execute(ctx.requests, request_id, message.from_user.id, delta)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()
        if not req:
            await message.answer("Заявка не найдена")
            return
        role = await _role(message.chat.id, message.from_user.id)
        await publish_request_event(
            ctx=ctx,
            publisher=publisher,
            chat_id=message.chat.id,
            request=req,
            reply_markup=request_actions_keyboard(req, role or Role.FOREMAN),
        )
        await message.answer("Получение (частично) зафиксировано")

    @router.callback_query(F.data.startswith("received_full:"))
    async def received_full_click(call: CallbackQuery) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.FOREMAN:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await confirm_full_received.execute(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=call.message.chat.id,
                request=req,
                reply_markup=None,
            )
        await call.answer("Заявка закрыта")

    return router
