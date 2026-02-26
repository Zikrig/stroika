from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.application.context import AppContext
from app.bot.routers import admin, common, foreman, manager, pdo, procurement
from app.infrastructure.telegram.publisher import TelegramPublisher


def create_dispatcher(bot: Bot, ctx: AppContext) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    publisher = TelegramPublisher(bot)
    dp.include_router(common.get_router(ctx))
    dp.include_router(foreman.get_router(ctx, publisher))
    dp.include_router(pdo.get_router(ctx, publisher))
    dp.include_router(procurement.get_router(ctx, publisher))
    dp.include_router(manager.get_router(ctx, publisher))
    dp.include_router(admin.get_router(ctx, publisher))
    return dp
