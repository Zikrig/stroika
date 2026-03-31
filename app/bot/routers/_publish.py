import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from app.application.context import AppContext
from app.bot.formatters.request_card import _fmt_date, render_container_card, render_request_card
from app.bot.keyboards.request_actions import request_actions_keyboard_group
from app.domain.enums import EventType
from app.infrastructure.telegram.publisher import TelegramPublisher

logger = logging.getLogger("bot.debug")


async def safe_update_request_in_group(
    ctx: AppContext,
    publisher: TelegramPublisher,
    request: dict,
    target_chat_id: int,
    *,
    source_message_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
    note: str = "",
    note_label: str = "Комментарий",
) -> str | None:
    """Обновляет карточку заявки в группе (редакт или публикация). Возвращает None при успехе, иначе строку ошибки (логирует исключение)."""
    try:
        if source_message_id is not None:
            try:
                await edit_request_message(
                    ctx=ctx,
                    publisher=publisher,
                    chat_id=target_chat_id,
                    message_id=source_message_id,
                    request=request,
                    reply_markup=reply_markup,
                    note=note or None,
                    note_label=note_label,
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in (e.message or "").lower():
                    raise
                # Текст и клавиатура не изменились — редактирование не требуется
            events = await ctx.requests.get_events(request["id"])
            if events:
                info = await ctx.requests.get_latest_message_info(request["id"], target_chat_id)
                ct = (info["content_type"] if info else "text")
                await ctx.requests.add_message_link(
                    request["id"], events[-1]["id"], target_chat_id, source_message_id, content_type=ct,
                )
            await publish_event_reply(
                ctx=ctx,
                publisher=publisher,
                chat_id=target_chat_id,
                request_id=request["id"],
                root_message_id=source_message_id,
                note=note or None,
                note_label=note_label,
            )
        else:
            await publish_request_event(
                ctx=ctx,
                publisher=publisher,
                chat_id=target_chat_id,
                request=request,
                reply_markup=reply_markup,
                note=note or None,
                note_label=note_label,
            )
        return None
    except Exception as e:
        logger.exception("safe_update_request_in_group request_id=%s: %s", request.get("id"), e)
        return "Действие сохранено, но не удалось обновить сообщение в группе."


async def get_request_actions_keyboard_group(ctx: AppContext, request: dict) -> InlineKeyboardMarkup | None:
    """Build group keyboard with 'В работе: Роль (@login)' when applicable."""
    events = await ctx.requests.get_events(request["id"])
    taken_by_pdo: dict | None = None
    taken_by_proc: dict | None = None
    for e in reversed(events or []):
        if e.get("event_type") == EventType.PDO_TAKEN.value and taken_by_pdo is None:
            uid = e.get("actor_user_id")
            if uid is not None:
                u = await ctx.roles.get_user(uid)
                taken_by_pdo = dict(u) if u else {"id": uid}
            break
    for e in reversed(events or []):
        if e.get("event_type") == EventType.PROCUREMENT_TAKEN.value and taken_by_proc is None:
            uid = e.get("actor_user_id")
            if uid is not None:
                u = await ctx.roles.get_user(uid)
                taken_by_proc = dict(u) if u else {"id": uid}
            break
    return request_actions_keyboard_group(
        request, taken_by_pdo=taken_by_pdo, taken_by_proc=taken_by_proc,
    )


async def _request_card_text(
    ctx: AppContext,
    request: dict,
    note: str | None = None,
    note_label: str = "Комментарий",
) -> str:
    events = await ctx.requests.get_events(request["id"])
    attachments_summary = await ctx.requests.get_attachment_summary(request["id"])
    foreman_info = None
    if request.get("foreman_user_id"):
        foreman_info = await ctx.roles.get_user(request["foreman_user_id"])
    return render_request_card(
        request,
        events=events,
        attachments_summary=attachments_summary,
        note=note,
        note_label=note_label,
        foreman_info=foreman_info,
    )


def _format_event_log_line(request: dict, event: dict, note: str | None, note_label: str) -> str:
    created = _fmt_date(event.get("created_at"))
    event_type = event.get("event_type")
    payload = event.get("payload_json") or {}

    parts: list[str] = []

    if event_type == EventType.REQUEST_CREATED.value:
        parts.append("Заявка создана")
    elif event_type == EventType.PDO_TAKEN.value:
        parts.append("ПДО взял(а) заявку в работу")
    elif event_type == EventType.PDO_FORMALIZED.value:
        mode = payload.get("mode")
        if mode == "container":
            count = payload.get("children_count")
            parts.append(f"ПДО сформировал контейнер, создано дочерних заявок: {count}")
        else:
            parts.append("ПДО обработал заявку")
    elif event_type == EventType.PROCUREMENT_TAKEN.value:
        parts.append("Закупка взяла заявку в работу")
    elif event_type == EventType.RETURNED_TO_PDO.value:
        parts.append("Заявка возвращена в ПДО")
    elif event_type == EventType.PURCHASED.value:
        eta = payload.get("eta_shipping")
        if eta:
            parts.append(f"Закуплено, поставка до офиса до {eta}")
        else:
            parts.append("Закуплено")
    elif event_type == EventType.SHIPPED.value:
        eta_arrival = payload.get("eta_arrival")
        if eta_arrival:
            parts.append(f"Отгружено, ожидаем на объект к {eta_arrival}")
        else:
            parts.append("Отгружено поставщиком")
    elif event_type == EventType.PARTIALLY_RECEIVED.value:
        delta = payload.get("delta_qty")
        total = payload.get("received_total_qty")
        remaining = payload.get("remaining_qty")
        parts.append(f"Прораб получил частично: +{delta} (итого {total}, остаток {remaining})")
    elif event_type == EventType.FULLY_RECEIVED.value:
        total = payload.get("received_total_qty")
        parts.append(f"Прораб получил полностью (всего {total})")
    elif event_type == EventType.CANCELLED.value:
        parts.append("Заявка отменена")
    elif event_type == EventType.PAUSED.value:
        parts.append("Заявка поставлена на паузу")
    elif event_type == EventType.RESUMED.value:
        parts.append("Пауза снята")
    elif event_type == EventType.MANAGER_COMMENTED.value:
        parts.append("Комментарий руководителя")
    elif event_type == EventType.TERMINATED.value:
        parts.append("Закупка прекращена руководителем")

    if note:
        parts.append(f"{note_label}: {note}")

    body = " | ".join(str(p) for p in parts if p) or f"Событие {event_type}"
    return f"{created} — {body}"


async def publish_event_reply(
    ctx: AppContext,
    publisher: TelegramPublisher,
    chat_id: int,
    request_id: str,
    root_message_id: int,
    note: str | None = None,
    note_label: str = "Комментарий",
) -> None:
    events = await ctx.requests.get_events(request_id)
    if not events:
        return
    last = events[-1]
    if last.get("event_type") == EventType.REQUEST_CREATED.value:
        # Для события создания заявки отдельное reply-сообщение не отправляем
        return
    text = _format_event_log_line({}, last, note=note, note_label=note_label)
    # Фото, привязанные к этому событию (например «Получено полностью» с фото поставки)
    attachments = await ctx.requests.list_attachments(request_id, event_id=last["id"])
    photo_file_ids = [
        a["file_id"] for a in attachments
        if a.get("attachment_type") == "photo" and a.get("file_id")
    ]
    if photo_file_ids:
        # Отправляем первое фото с подписью = строка лога; остальные — альбомом или по одному
        first_id = photo_file_ids[0]
        message_id = await publisher.send_photo(
            chat_id=chat_id,
            photo=first_id,
            caption=text,
            reply_to_message_id=root_message_id,
        )
        await ctx.requests.add_message_link(
            request_id, last["id"], chat_id, message_id, content_type="photo",
        )
        rest = photo_file_ids[1:10]
        if len(rest) == 1:
            try:
                mid = await publisher.send_photo(
                    chat_id=chat_id, photo=rest[0], reply_to_message_id=root_message_id,
                )
                await ctx.requests.add_message_link(
                    request_id, last["id"], chat_id, mid, content_type="photo",
                )
            except Exception:
                pass
        elif len(rest) >= 2:
            try:
                await publisher.send_media_group_photos(
                    chat_id=chat_id,
                    file_ids=rest,
                    reply_to_message_id=root_message_id,
                )
            except Exception:
                pass
    else:
        message_id = await publisher.publish(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=root_message_id,
        )
        await ctx.requests.add_message_link(
            request_id, last["id"], chat_id, message_id, content_type="text",
        )


async def publish_request_event(
    ctx: AppContext,
    publisher: TelegramPublisher,
    chat_id: int,
    request: dict,
    reply_markup: InlineKeyboardMarkup | None,
    note: str | None = None,
    note_label: str = "Комментарий",
    log_event: bool = True,
) -> int:
    """Publish or update request card in group.
    Основная карточка заявки — это одно сообщение (текст или фото+подпись).
    Отдельно для каждого события публикуется короткий лог-сообщение ответом на эту карточку.
    """
    text = await _request_card_text(ctx, request, note=note, note_label=note_label)
    existing = await ctx.requests.get_latest_message_info(request["id"], chat_id)
    if existing is not None:
        msg_id = existing["message_id"]
        content_type = existing["content_type"]
        if content_type == "photo":
            await publisher.edit_message_caption(
                chat_id=chat_id, message_id=msg_id, caption=text, reply_markup=reply_markup,
            )
        else:
            await publisher.edit_message(
                chat_id=chat_id, message_id=msg_id, text=text, reply_markup=reply_markup,
            )
        # Лог-сообщение по последнему событию
        if log_event:
            await publish_event_reply(
                ctx=ctx,
                publisher=publisher,
                chat_id=chat_id,
                request_id=request["id"],
                root_message_id=msg_id,
                note=note,
                note_label=note_label,
            )
        return msg_id
    attachments = await ctx.requests.list_attachments(request["id"])
    photo_file_ids = [
        a["file_id"] for a in attachments if a.get("attachment_type") == "photo" and a.get("file_id")
    ]
    if photo_file_ids:
        message_id = await publisher.send_photo(
            chat_id=chat_id,
            photo=photo_file_ids[0],
            caption=text,
            reply_markup=reply_markup,
        )
        content_type = "photo"
        rest_photos = photo_file_ids[1:10]
        if len(rest_photos) == 1:
            try:
                await publisher.send_photo(chat_id=chat_id, photo=rest_photos[0])
            except Exception:
                pass
        elif len(rest_photos) >= 2:
            try:
                await publisher.send_media_group_photos(chat_id=chat_id, file_ids=rest_photos)
            except Exception:
                pass
    else:
        message_id = await publisher.publish(chat_id=chat_id, text=text, reply_markup=reply_markup)
        content_type = "text"

    # Дополнительно: отправить голосовые сообщения, если они есть (отдельными сообщениями)
    voice_file_ids = [
        a["file_id"] for a in attachments if a.get("attachment_type") == "voice" and a.get("file_id")
    ]
    if voice_file_ids:
        events = await ctx.requests.get_events(request["id"])
        last_event_id = events[-1]["id"] if events else None
        for fid in voice_file_ids[:10]:
            try:
                v_msg_id = await publisher.send_voice(
                    chat_id=chat_id,
                    voice=fid,
                    reply_to_message_id=message_id,
                )
                if last_event_id is not None:
                    await ctx.requests.add_message_link(
                        request["id"], last_event_id, chat_id, v_msg_id, content_type="voice",
                    )
            except Exception:
                pass
    events = await ctx.requests.get_events(request["id"])
    if events:
        await ctx.requests.add_message_link(
            request["id"], events[-1]["id"], chat_id, message_id, content_type=content_type,
        )
    # Лог-сообщение по последнему событию
    if log_event:
        await publish_event_reply(
            ctx=ctx,
            publisher=publisher,
            chat_id=chat_id,
            request_id=request["id"],
            root_message_id=message_id,
            note=note,
            note_label=note_label,
        )
    return message_id


async def edit_request_message(
    ctx: AppContext,
    publisher: TelegramPublisher,
    chat_id: int,
    message_id: int,
    request: dict,
    reply_markup: InlineKeyboardMarkup | None,
    note: str | None = None,
    note_label: str = "Комментарий",
) -> None:
    """Update existing group message with new card and keyboard. Uses caption if message is photo."""
    text = await _request_card_text(ctx, request, note=note, note_label=note_label)
    # Тип контента берём именно для редактируемого сообщения (карточки), а не для
    # "последнего" в логе — иначе последним может быть ответ (голос/текст) и мы вызовем
    # edit_message_text для фото-карточки и получим "there is no text in the message to edit".
    content_type = await ctx.requests.get_message_content_type(request["id"], chat_id, message_id)
    try:
        if content_type == "photo":
            await publisher.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=reply_markup,
            )
        else:
            await publisher.edit_message(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
            )
    except TelegramBadRequest as e:
        msg = (e.message or "").lower()
        # Fallback на случай, когда в БД тип сохранён как text, а в Telegram это фото/медиа без текста.
        if "no text in the message to edit" in msg:
            await publisher.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=reply_markup,
            )
        else:
            raise


async def publish_container_event(
    ctx: AppContext,
    publisher: TelegramPublisher,
    chat_id: int,
    container: dict,
    child_codes: list[str],
    source_message_id: int | None = None,
) -> int:
    events = await ctx.requests.get_events(container["id"])
    text = render_container_card(container, child_codes)
    message_id = source_message_id
    if source_message_id is not None:
        try:
            await publisher.edit_message(
                chat_id=chat_id,
                message_id=source_message_id,
                text=text,
                reply_markup=None,
            )
        except TelegramBadRequest as e:
            msg = (e.message or "").lower()
            if "message is not modified" not in msg:
                message_id = None
    if message_id is None:
        message_id = await publisher.publish(chat_id=chat_id, text=text, reply_markup=None)
    if events:
        await ctx.requests.add_message_link(container["id"], events[-1]["id"], chat_id, message_id)
    await publish_event_reply(
        ctx=ctx,
        publisher=publisher,
        chat_id=chat_id,
        request_id=container["id"],
        root_message_id=message_id,
    )
    return message_id
