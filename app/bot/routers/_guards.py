from app.application.context import AppContext


async def is_latest_request_message(ctx: AppContext, request_id: str, chat_id: int, message_id: int) -> bool:
    """Проверка устаревшей карточки отключена.

    Сейчас по каждой заявке в группе есть ровно одна основная карточка,
    которая при изменениях только редактируется, а не дублируется.
    Поэтому блокировать действия по «устаревшей» карточке больше не требуется.
    """
    return True
