from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._migrations_dir = Path(__file__).with_name("migrations")

    async def connect(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.path)
        conn.row_factory = sqlite3.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        return conn

    async def migrate(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = await self.connect()
        try:
            for migration_file in sorted(self._migrations_dir.glob("*.sql")):
                sql = migration_file.read_text(encoding="utf-8")
                await conn.executescript(sql)
            await conn.commit()
        finally:
            await conn.close()

    @staticmethod
    def row_to_dict(row: sqlite3.Row | aiosqlite.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def dumps(data: dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def loads(data: str) -> dict[str, Any]:
        return json.loads(data)
