import asyncio
import logging

from app.infrastructure.repositories.outbox_repository import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxWorker:
    def __init__(self, outbox: OutboxRepository, retry_seconds: int = 30) -> None:
        self.outbox = outbox
        self.retry_seconds = retry_seconds
        self._running = False

    async def process_once(self) -> None:
        items = await self.outbox.fetch_pending(limit=50)
        for item in items:
            try:
                # Extension point: send item to Google Sheets or another sink.
                logger.info("Outbox processed topic=%s id=%s", item["topic"], item["id"])
                await self.outbox.mark_done(item["id"])
            except Exception:  # pragma: no cover - defensive path
                logger.exception("Outbox item failed id=%s", item["id"])
                await self.outbox.mark_retry(item["id"], item["retries"], self.retry_seconds)

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            await self.process_once()
            await asyncio.sleep(self.retry_seconds)

    def stop(self) -> None:
        self._running = False
