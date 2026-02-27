from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.application.context import AppContext


class ParticipantTrackingMiddleware(BaseMiddleware):
    """Upserts chat & user on every group message without consuming it."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if (
            isinstance(event, Message)
            and event.chat.type in ("group", "supergroup")
            and event.from_user
        ):
            await self.ctx.roles.upsert_chat(event.chat.id, event.chat.title or "Объект")
            await self.ctx.roles.upsert_user(
                event.from_user.id,
                event.from_user.username,
                event.from_user.full_name,
            )
        return await handler(event, data)
