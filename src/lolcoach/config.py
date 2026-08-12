from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    riot_api_key: str = ""
    anthropic_api_key: str = ""

    cache_dir: Path = Path("cache")
    db_path: Path = Path("lolcoach.db")

    riot_default_cluster: str = "americas"


@lru_cache
def get_settings() -> Settings:
    """Loaded lazily so importing this module never requires RIOT_API_KEY to be set."""
    return Settings()  # type: ignore[call-arg]
