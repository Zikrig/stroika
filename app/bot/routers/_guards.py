from app.application.context import AppContext


async def is_latest_request_message(ctx: AppContext, request_id: str, chat_id: int, message_id: int) -> bool:
    latest_message_id = await ctx.requests.get_latest_message_id(request_id=request_id, chat_id=chat_id)
    if latest_message_id is None:
        # Legacy rows may not have links yet; do not hard-block in that case.
        return True
    return latest_message_id == message_id
