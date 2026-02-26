from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup


class TelegramPublisher:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def publish(self, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> int:
        message = await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        return message.message_id
