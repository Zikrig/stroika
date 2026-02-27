import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger("bot.debug")


class HandlerLoggingMiddleware(BaseMiddleware):
    """Logs every handled update: type, chat, user, FSM state before/after."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        state: FSMContext | None = data.get("state")
        state_before = str(await state.get_state()) if state else "no-fsm"
        state_data_before = await state.get_data() if state else {}

        tag = _describe_event(event)
        logger.info("[>>] %s | state=%s | data_keys=%s", tag, state_before, list(state_data_before.keys()))

        try:
            result = await handler(event, data)
        except Exception:
            logger.exception("[!!] handler exception for %s", tag)
            raise

        state_after = str(await state.get_state()) if state else "no-fsm"
        state_data_after = await state.get_data() if state else {}

        if state_before != state_after:
            logger.info("[<<] %s | state CHANGED %s -> %s", tag, state_before, state_after)
        else:
            logger.info("[<<] %s | state unchanged %s", tag, state_after)

        if state_data_before != state_data_after:
            added = {k: v for k, v in state_data_after.items() if k not in state_data_before or state_data_before[k] != v}
            removed = {k for k in state_data_before if k not in state_data_after}
            logger.info("[<<] %s | data diff: added/changed=%s removed=%s", tag, added, removed)

        return result


def _describe_event(event: TelegramObject) -> str:
    if isinstance(event, Message):
        ct = event.content_type
        text_preview = (event.text or event.caption or "")[:60]
        return (
            f"MSG chat={event.chat.id} user={getattr(event.from_user, 'id', '?')} "
            f"type={ct} text={text_preview!r}"
        )
    if isinstance(event, CallbackQuery):
        return (
            f"CB chat={getattr(event.message, 'chat', {}).id if event.message else '?'} "
            f"user={event.from_user.id} data={event.data!r}"
        )
    return f"OTHER {type(event).__name__}"
