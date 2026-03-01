from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto


class TelegramPublisher:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def publish(self, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> int:
        message = await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        return message.message_id

    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> int:
        message = await self.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
        )
        return message.message_id

    async def send_media_group_photos(
        self, chat_id: int, file_ids: list[str], caption: str | None = None
    ) -> None:
        if not file_ids:
            return
        if len(file_ids) == 1:
            await self.bot.send_photo(
                chat_id=chat_id, photo=file_ids[0], caption=caption or "Фото к заявке"
            )
            return
        media = [InputMediaPhoto(media=fid) for fid in file_ids[:10]]
        if caption:
            media[0].caption = caption
        await self.bot.send_media_group(chat_id=chat_id, media=media)

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        await self.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )
