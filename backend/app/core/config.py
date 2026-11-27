from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "owe2me"
    environment: str = "development"
    debug: bool = False

    database_url: str = "mysql+pymysql://owe2me:owe2me@db:3306/owe2me?charset=utf8mb4"
    database_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
