from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputMediaPhoto


class TelegramPublisher:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def publish(
        self,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        message = await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
        return message.message_id

    async def send_photo(
        self,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        message = await self.bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
        return message.message_id

    async def send_media_group_photos(
        self,
        chat_id: int,
        file_ids: list[str],
        caption: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> None:
        if not file_ids:
            return
        media = [InputMediaPhoto(media=fid) for fid in file_ids[:10]]
        if caption:
            media[0].caption = caption
        await self.bot.send_media_group(chat_id=chat_id, media=media, reply_to_message_id=reply_to_message_id)

    async def send_voice(
        self,
        chat_id: int,
        voice: str,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        message = await self.bot.send_voice(
            chat_id=chat_id,
            voice=voice,
            caption=caption,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
        return message.message_id

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

    async def edit_message_caption(
        self,
        chat_id: int,
        message_id: int,
        caption: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        await self.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            reply_markup=reply_markup,
        )

    async def send_document(
        self,
        chat_id: int,
        document: str,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        message = await self.bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
        return message.message_id

    async def send_video(
        self,
        chat_id: int,
        video: str,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        message = await self.bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=caption,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
        return message.message_id

    async def send_audio(
        self,
        chat_id: int,
        audio: str,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        message = await self.bot.send_audio(
            chat_id=chat_id,
            audio=audio,
            caption=caption,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
        return message.message_id

    async def send_video_note(
        self,
        chat_id: int,
        video_note: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        message = await self.bot.send_video_note(
            chat_id=chat_id,
            video_note=video_note,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
        )
        return message.message_id
