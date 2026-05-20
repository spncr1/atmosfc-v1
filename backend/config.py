# AtmosFC configuration

from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent / ".env"

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    # Runtime settings loaded from environment variables.

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    football_data_api_key: str = Field(default="", alias="FOOTBALL_DATA_API_KEY")
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ORIGINS")

    @property
    def allowed_origins(self) -> List[str]:
        # Return configured CORS origins as a list.

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # Return cached application settings.

    return Settings()
