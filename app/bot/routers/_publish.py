from aiogram.types import InlineKeyboardMarkup

from app.application.context import AppContext
from app.bot.formatters.request_card import render_container_card, render_request_card
from app.bot.keyboards.request_actions import request_actions_keyboard_group
from app.domain.enums import EventType
from app.infrastructure.telegram.publisher import TelegramPublisher


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


async def publish_request_event(
    ctx: AppContext,
    publisher: TelegramPublisher,
    chat_id: int,
    request: dict,
    reply_markup: InlineKeyboardMarkup | None,
    note: str | None = None,
    note_label: str = "Комментарий",
) -> int:
    """Publish or update request card in group. One message: text or photo+caption. Prefer edit if exists."""
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
        events = await ctx.requests.get_events(request["id"])
        if events:
            await ctx.requests.add_message_link(
                request["id"], events[-1]["id"], chat_id, msg_id, content_type=content_type,
            )
        return msg_id
    attachments = await ctx.requests.list_attachments(request["id"])
    photo_file_ids = [a["file_id"] for a in attachments if a.get("attachment_type") == "photo" and a.get("file_id")]
    if photo_file_ids:
        message_id = await publisher.send_photo(
            chat_id=chat_id,
            photo=photo_file_ids[0],
            caption=text,
            reply_markup=reply_markup,
        )
        content_type = "photo"
    else:
        message_id = await publisher.publish(chat_id=chat_id, text=text, reply_markup=reply_markup)
        content_type = "text"
    events = await ctx.requests.get_events(request["id"])
    if events:
        await ctx.requests.add_message_link(
            request["id"], events[-1]["id"], chat_id, message_id, content_type=content_type,
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
    info = await ctx.requests.get_latest_message_info(request["id"], chat_id)
    content_type = (info["content_type"] if info and info["message_id"] == message_id else "text")
    if content_type == "photo":
        await publisher.edit_message_caption(
            chat_id=chat_id, message_id=message_id, caption=text, reply_markup=reply_markup,
        )
    else:
        await publisher.edit_message(
            chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup,
        )


async def publish_container_event(
    ctx: AppContext,
    publisher: TelegramPublisher,
    chat_id: int,
    container: dict,
    child_codes: list[str],
) -> int:
    events = await ctx.requests.get_events(container["id"])
    text = render_container_card(container, child_codes)
    message_id = await publisher.publish(chat_id=chat_id, text=text, reply_markup=None)
    if events:
        await ctx.requests.add_message_link(container["id"], events[-1]["id"], chat_id, message_id)
    return message_id
