# pyright: reportUnusedFunction=false
import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.application.context import AppContext
from app.application.use_cases import pdo_process_excel, take_request
from app.bot.keyboards.menus import cancel_inline, private_main_menu_inline
from app.bot.routers._guards import is_latest_request_message
from app.bot.routers._helpers import private_fsm
from app.bot.routers._publish import (
    get_request_actions_keyboard_group,
    publish_container_event,
    publish_request_event,
    safe_update_request_in_group,
)
from app.bot.states import ActionInputStates
from app.config import get_settings
from app.domain.enums import Role
from app.infrastructure.excel.parser import parse_pdo_excel
from app.infrastructure.excel.template_builder import build_pdo_template
from app.infrastructure.telegram.publisher import TelegramPublisher

logger = logging.getLogger("bot.debug")


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
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=group_chat_id,
                source_message_id=call.message.message_id,
                reply_markup=await get_request_actions_keyboard_group(ctx, req),
            )
            if err:
                await call.answer(err, show_alert=True)
                return
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

        try:
            req = await take_request.take_by_pdo(ctx.requests, request_id, call.from_user.id) or req
        except ValueError as exc:
            await call.answer(str(exc), show_alert=True)
            return
        if req:
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=req,
                target_chat_id=group_chat_id,
                source_message_id=call.message.message_id,
                reply_markup=await get_request_actions_keyboard_group(ctx, req),
            )
            if err:
                await call.answer(err, show_alert=True)
                return

        p_state = private_fsm(state, call.bot.id, call.from_user.id)
        await p_state.set_state(ActionInputStates.waiting_pdo_excel)
        await p_state.update_data(
            target_request_id=request_id,
            target_chat_id=group_chat_id,
            source_message_id=call.message.message_id,
        )

        foreman_info = None
        if req.get("foreman_user_id"):
            foreman_info = await ctx.roles.get_user(req["foreman_user_id"])
        foreman_display = (foreman_info.get("display_name") or foreman_info.get("full_name") or "").strip() if foreman_info else ""

        content = build_pdo_template(req, foreman_display_name=foreman_display)
        code = req["request_code"]
        filename_original = f"{code}.0.xlsx"
        caption = (
            "Заполните форму и отправьте файлом сюда (в личку бота).\n\n"
            f"Файл сохранён как «{filename_original}» — так в истории остаётся исходная заявка. "
            f"После обработки сохраните и присылайте форму уже с именем «{code}.xlsx» (без .0), "
            "чтобы по названию отличать обработанные заявки от исходных."
        )
        try:
            await call.bot.send_document(
                call.from_user.id,
                BufferedInputFile(content, filename=filename_original),
                caption=caption,
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
        filename = (message.document.file_name or "").strip()
        if ".0" in filename:
            await message.answer(
                "В имени файла не должно быть «.0». Переименуйте файл (например, в «код заявки.xlsx» без .0) и отправьте снова.",
                reply_markup=cancel_inline(),
            )
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
        source_message_id = data.get("source_message_id")
        await state.clear()

        code = req.get("request_code", "")
        hint = (
            f"Форма ПДО обработана. Напоминание: сохраняйте обработанные файлы под именем «{code}.xlsx» (без .0), "
            f"а исходный бланк у вас остаётся «{code}.0.xlsx» — так в истории на компьютере видно, что исходная заявка, а что обработанная."
        )

        if len(created) == 1 and source_message_id is not None:
            item = created[0]
            err = await safe_update_request_in_group(
                ctx=ctx,
                publisher=publisher,
                request=item,
                target_chat_id=target_chat_id,
                source_message_id=source_message_id,
                reply_markup=await get_request_actions_keyboard_group(ctx, item),
            )
            if err:
                await message.answer(err, reply_markup=await _menu(message.from_user.id))
                await message.answer(hint, reply_markup=await _menu(message.from_user.id))
                return
        else:
            try:
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
                        request=item, reply_markup=await get_request_actions_keyboard_group(ctx, item),
                    )
            except Exception as e:
                logger.exception("pdo_upload_excel: не удалось обновить группу (multi): %s", e)
                await message.answer(
                    "Форма обработана, но не удалось обновить сообщения в группе.",
                    reply_markup=await _menu(message.from_user.id),
                )
        await message.answer(hint, reply_markup=await _menu(message.from_user.id))

    @router.message(ActionInputStates.waiting_pdo_excel, F.chat.type == "private")
    async def pdo_excel_not_document(message: Message) -> None:
        await message.answer(
            "Ожидается файл Excel.\nОтправьте документ (файл), а не текст/фото.",
            reply_markup=cancel_inline(),
        )

    return router
