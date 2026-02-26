import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.infrastructure.db.sqlite import Database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OutboxRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def push(self, topic: str, payload: dict[str, Any]) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO outbox(id, topic, payload_json, status, next_retry_at, created_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (str(uuid.uuid4()), topic, self.db.dumps(payload), _now_iso(), _now_iso()),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def fetch_pending(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                """
                SELECT * FROM outbox
                WHERE status='pending' AND next_retry_at <= CURRENT_TIMESTAMP
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["payload_json"] = self.db.loads(item["payload_json"])
                result.append(item)
            return result
        finally:
            await conn.close()

    async def mark_done(self, item_id: str) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                "UPDATE outbox SET status='done', processed_at=? WHERE id=?",
                (_now_iso(), item_id),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def mark_retry(self, item_id: str, retries: int, retry_after_seconds: int) -> None:
        conn = await self.db.connect()
        try:
            next_dt = (datetime.now(timezone.utc) + timedelta(seconds=retry_after_seconds)).isoformat()
            await conn.execute(
                "UPDATE outbox SET retries=?, next_retry_at=? WHERE id=?",
                (retries + 1, next_dt, item_id),
            )
            await conn.commit()
        finally:
            await conn.close()
