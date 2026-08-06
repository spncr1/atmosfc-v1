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

    api_football_key: str = Field(default="", alias="API_FOOTBALL_KEY")
    api_football_base_url: str = Field(default="https://v3.football.api-sports.io", alias="API_FOOTBALL_BASE_URL")
    wikidata_api_url: str = Field(default="https://www.wikidata.org/w/api.php", alias="WIKIDATA_API_URL")
    wikidata_entity_data_url: str = Field(
        default="https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json",
        alias="WIKIDATA_ENTITY_DATA_URL",
    )
    wikimedia_user_agent: str = Field(
        default="AtmosFC/0.1 (https://atmosfc-v1.vercel.app)",
        alias="WIKIMEDIA_USER_AGENT",
    )
    football_data_api_key: str = Field(default="", alias="FOOTBALL_DATA_API_KEY")
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    database_url: str = Field(default="", alias="DATABASE_URL")
    direct_database_url: str = Field(default="", alias="DIRECT_DATABASE_URL")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,https://atmosfc-v1.vercel.app",
        alias="CORS_ORIGINS",
    )

    @property
    def allowed_origins(self) -> List[str]:
        # Return configured CORS origins as a list.

        origins = []
        for origin in self.cors_origins.split(","):
            clean = origin.strip().rstrip("/")
            if clean:
                origins.append(clean)
        return origins


@lru_cache
def get_settings() -> Settings:
    # Return cached application settings.

    return Settings()
