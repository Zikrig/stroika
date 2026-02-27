from aiogram.types import InlineKeyboardMarkup

from app.application.context import AppContext
from app.bot.formatters.request_card import render_container_card, render_request_card
from app.infrastructure.telegram.publisher import TelegramPublisher


async def publish_request_event(
    ctx: AppContext,
    publisher: TelegramPublisher,
    chat_id: int,
    request: dict,
    reply_markup: InlineKeyboardMarkup | None,
    note: str | None = None,
    note_label: str = "Комментарий",
) -> int:
    events = await ctx.requests.get_events(request["id"])
    attachments_summary = await ctx.requests.get_attachment_summary(request["id"])
    foreman_info = None
    if request.get("foreman_user_id"):
        foreman_info = await ctx.roles.get_user(request["foreman_user_id"])
    text = render_request_card(
        request,
        events=events,
        attachments_summary=attachments_summary,
        note=note,
        note_label=note_label,
        foreman_info=foreman_info,
    )
    message_id = await publisher.publish(chat_id=chat_id, text=text, reply_markup=reply_markup)
    if events:
        await ctx.requests.add_message_link(request["id"], events[-1]["id"], chat_id, message_id)
    return message_id


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
