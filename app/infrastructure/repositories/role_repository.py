from app.domain.enums import Role
from app.infrastructure.db.sqlite import Database


class RoleRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def upsert_chat(self, chat_id: int, title: str) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO chats(id, title) VALUES(?, ?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title
                """,
                (chat_id, title),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def upsert_user(self, user_id: int, username: str | None, full_name: str) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO users(id, username, full_name) VALUES(?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name
                """,
                (user_id, username, full_name),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def set_role(self, chat_id: int, user_id: int, role: Role) -> None:
        # Keep chat-level record for backward compatibility and audits.
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO chat_roles(chat_id, user_id, role) VALUES(?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET role=excluded.role
                """,
                (chat_id, user_id, role.value),
            )
            await conn.execute(
                """
                INSERT INTO user_roles(user_id, role) VALUES(?, ?)
                ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, updated_at=CURRENT_TIMESTAMP
                """,
                (user_id, role.value),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_role(self, chat_id: int, user_id: int) -> Role | None:
        conn = await self.db.connect()
        try:
            cur_global = await conn.execute(
                "SELECT role FROM user_roles WHERE user_id=?",
                (user_id,),
            )
            global_row = await cur_global.fetchone()
            if global_row:
                return Role(global_row["role"])
            cur = await conn.execute(
                "SELECT role FROM chat_roles WHERE chat_id=? AND user_id=?",
                (chat_id, user_id),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return Role(row["role"])
        finally:
            await conn.close()

    async def set_global_role(self, user_id: int, role: Role) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                """
                INSERT INTO user_roles(user_id, role) VALUES(?, ?)
                ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, updated_at=CURRENT_TIMESTAMP
                """,
                (user_id, role.value),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_global_role(self, user_id: int) -> Role | None:
        conn = await self.db.connect()
        try:
            cur = await conn.execute("SELECT role FROM user_roles WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row:
                return None
            return Role(row["role"])
        finally:
            await conn.close()

    async def set_display_name(self, user_id: int, display_name: str) -> None:
        conn = await self.db.connect()
        try:
            await conn.execute(
                "UPDATE users SET display_name=? WHERE id=?",
                (display_name, user_id),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def get_user(self, user_id: int) -> dict | None:
        conn = await self.db.connect()
        try:
            cur = await conn.execute("SELECT * FROM users WHERE id=?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None
        finally:
            await conn.close()

    async def list_chats(self) -> list[dict]:
        conn = await self.db.connect()
        try:
            cur = await conn.execute(
                "SELECT id, title, created_at FROM chats ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()
            return [dict(row) for row in rows]
        finally:
            await conn.close()
