from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.domain.enums import EventType, Role, StageCode, StatusCode
from app.infrastructure.db.sqlite import Database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RequestRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def get_last_parent_code(self) -> str | None:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                "SELECT request_code FROM requests WHERE parent_request_id IS NULL ORDER BY created_at DESC LIMIT 1"
            )
            row = await cur.fetchone()
            return None if row is None else row["request_code"]
        finally:
            await conn.close()

    async def create_request(self, payload: dict[str, Any]) -> str:
        request_id = str(uuid.uuid4())
        conn = await self.db.connect()
        try:
            await conn.execute(
                "INSERT OR IGNORE INTO chats(id, title) VALUES(?, ?)",
                (payload["chat_id"], payload.get("object_name", "Объект")),
            )
            if payload.get("foreman_user_id") is not None:
                await conn.execute(
                    "INSERT OR IGNORE INTO users(id, username, full_name) VALUES(?, NULL, ?)",
                    (payload["foreman_user_id"], f"user_{payload['foreman_user_id']}"),
                )
            await conn.execute(
                """
                INSERT INTO requests (
                  id, request_code, chat_id, parent_request_id, is_container, foreman_user_id,
                  object_name, subobject_name, name_from_foreman, nomenclature_1c, code_1c,
                  requested_qty, unit, need_by, from_stock_qty, to_purchase_qty, received_total_qty,
                  remaining_qty, status_code, stage_code, responsible_role, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    payload["request_code"],
                    payload["chat_id"],
                    payload.get("parent_request_id"),
                    int(payload.get("is_container", False)),
                    payload.get("foreman_user_id"),
                    payload.get("object_name", "Объект"),
                    payload.get("subobject_name"),
                    payload.get("name_from_foreman"),
                    payload.get("nomenclature_1c"),
                    payload.get("code_1c"),
                    payload.get("requested_qty", 0.0),
                    payload.get("unit", "шт"),
                    payload.get("need_by"),
                    payload.get("from_stock_qty", 0.0),
                    payload.get("to_purchase_qty", 0.0),
                    payload.get("received_total_qty", 0.0),
                    payload.get("remaining_qty", payload.get("requested_qty", 0.0)),
                    payload.get("status_code", StatusCode.WAITING.value),
                    payload.get("stage_code", StageCode.CREATED.value),
                    payload.get("responsible_role", Role.PDO.value),
                    _now_iso(),
                    _now_iso(),
                ),
            )
            await conn.commit()
            return request_id
        finally:
            await conn.close()

    async def get_request_by_code(self, chat_id: int, request_code: str) -> dict[str, Any] | None:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                "SELECT * FROM requests WHERE chat_id=? AND request_code=?",
                (chat_id, request_code),
            )
            row = await cur.fetchone()
            return self.db.row_to_dict(row)
        finally:
            await conn.close()

    async def get_request(self, request_id: str) -> dict[str, Any] | None:
        conn = await self.db.connect()
        try:
            cur = await conn.execute("SELECT * FROM requests WHERE id=?", (request_id,))
            row = await cur.fetchone()
            return self.db.row_to_dict(row)
        finally:
            await conn.close()

    async def list_requests(self, chat_id: int, archived: bool = False, search: str | None = None) -> list[dict[str, Any]]:
        conn = await self.db.connect()
        try:
            sql = "SELECT * FROM requests WHERE chat_id=?"
            params: list[Any] = [chat_id]
            if archived:
                sql += " AND status_code IN (?, ?, ?)"
                params.extend([StatusCode.CLOSED.value, StatusCode.CANCELLED.value, StatusCode.TERMINATED.value])
            else:
                sql += " AND status_code NOT IN (?, ?, ?)"
                params.extend([StatusCode.CLOSED.value, StatusCode.CANCELLED.value, StatusCode.TERMINATED.value])
            if search:
                sql += " AND (request_code LIKE ? OR COALESCE(name_from_foreman, '') LIKE ? OR COALESCE(nomenclature_1c, '') LIKE ?)"
                like = f"%{search}%"
                params.extend([like, like, like])
            sql += " ORDER BY created_at DESC LIMIT 50"
            cur = await conn.execute(sql, tuple(params))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    async def append_event(
        self,
        request_id: str,
        event_type: EventType,
        actor_user_id: int,
        actor_role: Role,
        payload: dict[str, Any],
    ) -> str:
        event_id = str(uuid.uuid4())
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO request_events (id, request_id, event_type, actor_user_id, actor_role, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    request_id,
                    event_type.value,
                    actor_user_id,
                    actor_role.value,
                    self.db.dumps(payload),
                    _now_iso(),
                ),
            )
            await conn.execute(
                """
                INSERT INTO outbox(id, topic, payload_json, status, next_retry_at, created_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    "request_event",
                    self.db.dumps(
                        {
                            "event_id": event_id,
                            "request_id": request_id,
                            "event_type": event_type.value,
                            "actor_user_id": actor_user_id,
                            "actor_role": actor_role.value,
                            "payload": payload,
                        }
                    ),
                    _now_iso(),
                    _now_iso(),
                ),
            )
            await conn.commit()
            return event_id
        finally:
            await conn.close()

    async def update_state(
        self,
        request_id: str,
        status: StatusCode,
        stage: StageCode,
        responsible_role: Role | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        data = extra or {}
        fields = [
            "status_code=?",
            "stage_code=?",
            "responsible_role=?",
            "updated_at=?",
        ]
        params: list[Any] = [status.value, stage.value, None if responsible_role is None else responsible_role.value, _now_iso()]
        for key, value in data.items():
            fields.append(f"{key}=?")
            params.append(value)
        params.append(request_id)
        sql = f"UPDATE requests SET {', '.join(fields)} WHERE id=?"
        conn = await self.db.connect()
        try:
            await conn.execute(sql, tuple(params))
            await conn.commit()
        finally:
            await conn.close()

    async def add_message_link(self, request_id: str, event_id: str, chat_id: int, message_id: int) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO request_messages(request_id, event_id, chat_id, message_id)
                VALUES (?, ?, ?, ?)
                """,
                (request_id, event_id, chat_id, message_id),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_latest_message_id(self, request_id: str, chat_id: int) -> int | None:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                """
                SELECT message_id
                FROM request_messages
                WHERE request_id=? AND chat_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (request_id, chat_id),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            return int(row["message_id"])
        finally:
            await conn.close()

    async def get_events(self, request_id: str) -> list[dict[str, Any]]:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                "SELECT * FROM request_events WHERE request_id=? ORDER BY created_at ASC",
                (request_id,),
            )
            rows = await cur.fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["payload_json"] = self.db.loads(item["payload_json"])
                out.append(item)
            return out
        finally:
            await conn.close()

    async def get_events_with_attachment_counts(self, request_id: str) -> list[dict[str, Any]]:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                """
                SELECT
                  e.id,
                  e.request_id,
                  e.event_type,
                  e.actor_user_id,
                  e.actor_role,
                  e.payload_json,
                  e.created_at,
                  COUNT(a.id) AS attachments_count
                FROM request_events e
                LEFT JOIN request_attachments a ON a.event_id = e.id
                WHERE e.request_id=?
                GROUP BY e.id, e.request_id, e.event_type, e.actor_user_id, e.actor_role, e.payload_json, e.created_at
                ORDER BY e.created_at ASC
                """,
                (request_id,),
            )
            rows = await cur.fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["payload_json"] = self.db.loads(item["payload_json"])
                out.append(item)
            return out
        finally:
            await conn.close()

    async def insert_request_item(self, request_id: str, line_index: int, row: dict[str, Any]) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO request_items(id, request_id, line_index, nomenclature_1c, code_1c, requested_qty, unit, from_stock_qty, to_purchase_qty)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    request_id,
                    line_index,
                    row["nomenclature_1c"],
                    row["code_1c"],
                    row["requested_qty"],
                    row["unit"],
                    row["from_stock_qty"],
                    row["to_purchase_qty"],
                ),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def add_attachments(self, request_id: str, event_id: str | None, attachments: list[dict[str, Any]]) -> None:
        if not attachments:
            return
        conn = await self.db.connect()
        try:
            for item in attachments:
                await conn.execute(
                    """
                    INSERT INTO request_attachments(id, request_id, event_id, file_id, file_unique_id, attachment_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        request_id,
                        event_id,
                        item["file_id"],
                        item.get("file_unique_id"),
                        item["attachment_type"],
                    ),
                )
            await conn.commit()
        finally:
            await conn.close()

    async def list_attachments(self, request_id: str, event_id: str | None = None) -> list[dict[str, Any]]:
        conn = await self.db.connect()
        try:
            if event_id is None:
                cur = await conn.execute(
                    """
                    SELECT id, request_id, event_id, file_id, file_unique_id, attachment_type, created_at
                    FROM request_attachments
                    WHERE request_id=?
                    ORDER BY created_at ASC
                    """,
                    (request_id,),
                )
            else:
                cur = await conn.execute(
                    """
                    SELECT id, request_id, event_id, file_id, file_unique_id, attachment_type, created_at
                    FROM request_attachments
                    WHERE request_id=? AND event_id=?
                    ORDER BY created_at ASC
                    """,
                    (request_id, event_id),
                )
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def get_attachment_summary(self, request_id: str) -> dict[str, Any]:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                """
                SELECT attachment_type, COUNT(*) AS cnt
                FROM request_attachments
                WHERE request_id=?
                GROUP BY attachment_type
                ORDER BY attachment_type
                """,
                (request_id,),
            )
            rows = await cur.fetchall()
            by_type = {row["attachment_type"]: row["cnt"] for row in rows}
            total = int(sum(by_type.values()))
            return {"total": total, "by_type": by_type}
        finally:
            await conn.close()
