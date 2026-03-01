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
    """Publish or update request card in group. Prefer editing existing message if any."""
    text = await _request_card_text(ctx, request, note=note, note_label=note_label)
    existing_message_id = await ctx.requests.get_latest_message_id(request["id"], chat_id)
    if existing_message_id is not None:
        await publisher.edit_message(
            chat_id=chat_id,
            message_id=existing_message_id,
            text=text,
            reply_markup=reply_markup,
        )
        events = await ctx.requests.get_events(request["id"])
        if events:
            await ctx.requests.add_message_link(
                request["id"], events[-1]["id"], chat_id, existing_message_id
            )
        return existing_message_id
    message_id = await publisher.publish(chat_id=chat_id, text=text, reply_markup=reply_markup)
    events = await ctx.requests.get_events(request["id"])
    if events:
        await ctx.requests.add_message_link(request["id"], events[-1]["id"], chat_id, message_id)
    # Только при первой публикации: отправить вложения заявки в группу (сразу под карточкой)
    attachments = await ctx.requests.list_attachments(request["id"])
    photo_file_ids = [a["file_id"] for a in attachments if a.get("attachment_type") == "photo" and a.get("file_id")]
    if photo_file_ids:
        try:
            await publisher.send_media_group_photos(
                chat_id=chat_id, file_ids=photo_file_ids, caption="Фото к заявке",
            )
        except Exception:
            pass
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
    """Update existing group message with new card and keyboard (no new message)."""
    text = await _request_card_text(ctx, request, note=note, note_label=note_label)
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
