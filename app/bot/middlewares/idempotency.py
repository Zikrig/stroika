from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.infrastructure.repositories.update_repository import UpdateRepository


class IdempotencyMiddleware(BaseMiddleware):
    def __init__(self, updates: UpdateRepository) -> None:
        self.updates = updates

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Update) and event.update_id is not None:
            allowed = await self.updates.mark_processed(event.update_id)
            if not allowed:
                return None
        return await handler(event, data)
