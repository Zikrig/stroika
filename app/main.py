import asyncio
import logging

from aiogram import Bot

from app.application.context import AppContext
from app.bot.factory import create_dispatcher
from app.bot.middlewares.idempotency import IdempotencyMiddleware
from app.config import get_settings
from app.infrastructure.db.sqlite import Database
from app.infrastructure.outbox.worker import OutboxWorker
from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.infrastructure.repositories.request_repository import RequestRepository
from app.infrastructure.repositories.role_repository import RoleRepository
from app.infrastructure.repositories.update_repository import UpdateRepository
from app.logging import setup_logging


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    db = Database(settings.database_path)
    await db.migrate()

    requests = RequestRepository(db)
    roles = RoleRepository(db)
    outbox = OutboxRepository(db)
    updates = UpdateRepository(db)
    ctx = AppContext(requests=requests, roles=roles, outbox=outbox)

    bot = Bot(token=settings.bot_token)
    dp = create_dispatcher(bot, ctx)
    dp.update.middleware(IdempotencyMiddleware(updates))

    worker = OutboxWorker(outbox=outbox, retry_seconds=settings.outbox_retry_seconds)
    worker_task = asyncio.create_task(worker.run_forever())
    try:
        logging.getLogger(__name__).info("Bot started")
        await dp.start_polling(bot)
    finally:
        worker.stop()
        worker_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
