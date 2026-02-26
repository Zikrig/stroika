from app.infrastructure.db.sqlite import Database


class UpdateRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def mark_processed(self, update_id: int) -> bool:
        conn = await self.db.connect()
        try:
            try:
                await conn.execute(
                    "INSERT INTO processed_updates(update_id) VALUES (?)",
                    (update_id,),
                )
                await conn.commit()
                return True
            except Exception:
                return False
        finally:
            await conn.close()
