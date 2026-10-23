from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.5-plus-02-15")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    app_name: str = os.getenv("APP_NAME", "peru-legal-rag-data")
    worker_timezone: str = os.getenv("WORKER_TIMEZONE", "America/Lima")
    worker_schedule_hour: int = int(os.getenv("WORKER_SCHEDULE_HOUR", "10"))


def get_settings() -> Settings:
    return Settings()
