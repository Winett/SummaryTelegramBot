from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    telegram_token: str = Field(alias="TELEGRAM_TOKEN")
    admins: list[int] = Field(alias="ADMINS")

    db_user: str = Field(alias="DB_USER")
    db_password: str = Field(alias="DB_PASSWORD")
    db_host: str = Field(alias="DB_HOST")
    db_port: int = Field(alias="DB_PORT")
    db_name: str = Field(alias="DB_NAME")

    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")

    redis_host: str = Field(alias="REDIS_HOST", default="localhost")
    redis_port: int = Field(alias="REDIS_PORT", default=6379)
    redis_db: int = Field(alias="REDIS_DB", default=0)

    debug: bool = Field(alias="DEBUG")

    model_config =  SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()