import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Explicitly load backend/.env.local into process environment variables.
#load_dotenv(_BACKEND_ROOT / ".env.local")


class Settings(BaseSettings):
    app_name: str = Field(default="MediBot API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    auth_secret: str = Field(default="change-this-in-production", alias="AUTH_SECRET")
    sqlite_db_path: str = Field(default=str(_BACKEND_ROOT / "mediassist_data" / "db" / "mediassist.db"), alias="SQLITE_DB_PATH")
    knowledge_base_path: str = Field(default=str(_BACKEND_ROOT / "mediassist_data"), alias="KNOWLEDGE_BASE_PATH")
    qdrant_path: str = Field(default=str(_BACKEND_ROOT / ".qdrant_ingest_v1"), alias="QDRANT_PATH")
    qdrant_ingest_path: str = Field(default=str(_BACKEND_ROOT / ".qdrant_ingest_v1"), alias="QDRANT_INGEST_PATH")
    qdrant_collection_name: str = Field(default="mediassist_kb", alias="QDRANT_COLLECTION_NAME")
    enable_qdrant: bool = Field(default=True, alias="ENABLE_QDRANT")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")
    groq_temperature: float = Field(default=0.1, alias="GROQ_TEMPERATURE")
    allowed_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ],
        alias="ALLOWED_ORIGINS",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
