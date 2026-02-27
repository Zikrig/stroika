# pyright: reportUnusedFunction=false
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import pdo_process_excel, take_request
from app.bot.keyboards.menus import cancel_inline, private_main_menu_inline
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._helpers import private_fsm
from app.bot.keyboards.request_actions import request_actions_keyboard_group
from app.bot.routers._publish import publish_container_event, publish_request_event
from app.bot.states import ActionInputStates
from app.config import get_settings
from app.domain.enums import Role
from app.infrastructure.excel.parser import parse_pdo_excel
from app.infrastructure.excel.template_builder import build_pdo_template
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="pdo")
    admin_ids = set(get_settings().admin_id_list)

    async def _role(user_id: int) -> Role | None:
        return await ctx.roles.get_global_role(user_id)

    async def _menu(uid: int):
        role = await _role(uid)
        return private_main_menu_inline(role=role, is_admin=uid in admin_ids)

    # ── Take (one-click, group card) ──────────────────────────────────

    @router.callback_query(F.data.startswith("take_pdo:"))
    async def take_pdo(call: CallbackQuery) -> None:
        role = await _role(call.from_user.id)
        if role != Role.PDO:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await take_request.take_by_pdo(ctx.requests, request_id, call.from_user.id)
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            await publish_request_event(
                ctx=ctx, publisher=publisher, chat_id=group_chat_id,
                request=req, reply_markup=request_actions_keyboard_group(req),
            )
        await call.answer("Заявка взята ПДО")

    # ── Template + Excel upload (group card → DM FSM) ─────────────────

    @router.callback_query(F.data.startswith("pdo_template:"))
    async def pdo_template(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.from_user.id)
        if role != Role.PDO:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        group_chat_id = call.message.chat.id
        if not await is_latest_request_message(ctx, request_id, group_chat_id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        req = await ctx.requests.get_request(request_id)
        if not req:
            await call.answer("Заявка не найдена", show_alert=True)
            return

        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_pdo_excel)
        await p_state.update_data(
            target_request_id=request_id,
            target_chat_id=group_chat_id,
            source_message_id=call.message.message_id,
        )

        content = build_pdo_template(req["request_code"])
        try:
            await call.bot.send_document(
                call.from_user.id,
                BufferedInputFile(content, filename=f"{req['request_code']}.xlsx"),
                caption="Заполните форму и отправьте файлом сюда (в личку бота)",
                reply_markup=cancel_inline(),
            )
        except Exception:
            await call.answer("Сначала напишите /start боту в личку", show_alert=True)
            await p_state.clear()
            return
        await call.answer("Форма отправлена в личные сообщения")

    @router.message(ActionInputStates.waiting_pdo_excel, F.document, F.chat.type == "private")
    async def pdo_upload_excel(message: Message, state: FSMContext) -> None:
        role = await _role(message.from_user.id)
        if role != Role.PDO:
            await message.answer("Только роль ПДО может загрузить форму")
            return
        data = await state.get_data()
        request_id = data.get("target_request_id")
        target_chat_id = data["target_chat_id"]
        req = await ctx.requests.get_request(request_id)
        if not req:
            await message.answer("Заявка не найдена")
            await state.clear()
            return

        file_info = await message.bot.get_file(message.document.file_id)
        stream = BytesIO()
        await message.bot.download(file_info, destination=stream)
        try:
            rows = parse_pdo_excel(stream.getvalue())
        except Exception as exc:
            await message.answer(f"Ошибка формы Excel: {exc}")
            return
        try:
            created = await pdo_process_excel.execute(ctx.requests, req, rows, message.from_user.id)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.clear()

        if len(created) > 1:
            parent = await ctx.requests.get_request(request_id)
            if parent:
                await publish_container_event(
                    ctx=ctx, publisher=publisher, chat_id=target_chat_id,
                    container=parent, child_codes=[item["request_code"] for item in created],
                )

        for item in created:
            await publish_request_event(
                ctx=ctx, publisher=publisher, chat_id=target_chat_id,
                request=item, reply_markup=request_actions_keyboard_group(item),
            )
        await message.answer("Форма ПДО обработана", reply_markup=await _menu(message.from_user.id))

    @router.message(ActionInputStates.waiting_pdo_excel, F.chat.type == "private")
    async def pdo_excel_not_document(message: Message) -> None:
        await message.answer(
            "Ожидается файл Excel.\nОтправьте документ (файл), а не текст/фото.",
            reply_markup=cancel_inline(),
        )

    return router
