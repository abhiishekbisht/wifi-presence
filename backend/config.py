"""
Application configuration using Pydantic Settings.
"""
import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "Wi-Fi Classroom Presence Estimation"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = False
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'database' / 'wifi_presence.db'}"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="allow",
    )

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def allowed_origins(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def sqlite_db_path(self) -> Path:
        """Extract Path from sqlite:/// URI or fallback to default DB location."""
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "", 1)
            path_obj = Path(raw_path)
            if not path_obj.is_absolute():
                path_obj = BASE_DIR / path_obj
            return path_obj
        return BASE_DIR / "database" / "wifi_presence.db"


settings = Settings()


