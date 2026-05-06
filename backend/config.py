# AtmosFC configuration

from functools import lru_cache
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    # Runtime settings loaded from environment variables.

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    football_data_api_key: str = Field(default="", alias="FOOTBALL_DATA_API_KEY")
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="atmosfc:v1 (by /u/atmosfc)", alias="REDDIT_USER_AGENT")
    cors_origins: str = Field(default="http://localhost:8000,http://127.0.0.1:8000", alias="CORS_ORIGINS")

    @property
    def allowed_origins(self) -> List[str]:
        # Return configured CORS origins as a list.

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # Return cached application settings.

    return Settings()
