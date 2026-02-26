from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str = Field(alias="BOT_TOKEN")
    database_path: str = Field(default="data/app.db", alias="DATABASE_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    tz: str = Field(default="Europe/Moscow", alias="TZ")
    admin_ids: str = Field(default="", alias="ADMIN_IDS")
    outbox_retry_seconds: int = Field(default=30, alias="OUTBOX_RETRY_SECONDS")
    enable_gsheets: bool = Field(default=False, alias="ENABLE_GSHEETS")

    @property
    def admin_id_list(self) -> list[int]:
        if not self.admin_ids.strip():
            return []
        return [int(v.strip()) for v in self.admin_ids.split(",") if v.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
