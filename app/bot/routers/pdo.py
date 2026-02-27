from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import pdo_process_excel, take_request
from app.bot.keyboards.menus import cancel_inline
from app.bot.routers._guards import is_latest_request_message
from app.bot.keyboards.request_actions import request_actions_keyboard
from app.bot.routers._publish import publish_container_event, publish_request_event
from app.bot.states import ActionInputStates
from app.domain.enums import Role
from app.infrastructure.excel.parser import parse_pdo_excel
from app.infrastructure.excel.template_builder import build_pdo_template
from app.infrastructure.telegram.publisher import TelegramPublisher


def get_router(ctx: AppContext, publisher: TelegramPublisher) -> Router:
    router = Router(name="pdo")

    async def _role(chat_id: int, user_id: int) -> Role | None:
        return await ctx.roles.get_role(chat_id, user_id)

    @router.callback_query(F.data.startswith("take_pdo:"))
    async def take_pdo(call: CallbackQuery) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.PDO:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        try:
            req = await take_request.take_by_pdo(ctx.requests, request_id, call.from_user.id)
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
        await call.answer("Заявка взята ПДО")

    @router.callback_query(F.data.startswith("pdo_template:"))
    async def pdo_template(call: CallbackQuery, state: FSMContext) -> None:
        role = await _role(call.message.chat.id, call.from_user.id)
        if role != Role.PDO:
            await call.answer("Недостаточно прав", show_alert=True)
            return
        request_id = call.data.split(":", maxsplit=1)[1]
        if not await is_latest_request_message(ctx, request_id, call.message.chat.id, call.message.message_id):
            await call.answer("Карточка устарела. Используйте последнее сообщение по заявке.", show_alert=True)
            return
        req = await ctx.requests.get_request(request_id)
        if not req:
            await call.answer("Заявка не найдена", show_alert=True)
            return
        content = build_pdo_template(req["request_code"])
        await call.message.answer_document(
            BufferedInputFile(content, filename=f"{req['request_code']}.xlsx"),
            caption="Заполните форму и отправьте файлом в этот чат",
            reply_markup=cancel_inline(),
        )
        await state.set_state(ActionInputStates.waiting_pdo_excel)
        await state.update_data(target_request_id=request_id, source_message_id=call.message.message_id)
        await call.answer()

    @router.message(ActionInputStates.waiting_pdo_excel, F.document)
    async def pdo_upload_excel(message: Message, state: FSMContext) -> None:
        role = await _role(message.chat.id, message.from_user.id)
        if role != Role.PDO:
            await message.answer("Только роль ПДО может загрузить форму")
            return
        data = await state.get_data()
        request_id = data.get("target_request_id")
        source_message_id = int(data.get("source_message_id", 0))
        if source_message_id and not await is_latest_request_message(
            ctx, request_id, message.chat.id, source_message_id
        ):
            await message.answer("Карточка устарела. Нажмите действие на последнем сообщении по заявке.")
            await state.clear()
            return
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
                    ctx=ctx,
                    publisher=publisher,
                    chat_id=message.chat.id,
                    container=parent,
                    child_codes=[item["request_code"] for item in created],
                )

        for item in created:
            role_for_buttons = Role.PROCUREMENT if item["stage_code"] == "transferred_to_procurement" else Role.PDO
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=message.chat.id,
                request=item,
                reply_markup=request_actions_keyboard(item, role_for_buttons),
            )
        await message.answer("Форма ПДО обработана")

    @router.message(ActionInputStates.waiting_pdo_excel)
    async def pdo_excel_not_document(message: Message) -> None:
        await message.answer(
            "Ожидается файл Excel.\n"
            "Отправьте документ (файл), а не текст/фото.",
            reply_markup=cancel_inline(),
        )

    return router
