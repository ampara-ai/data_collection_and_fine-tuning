from __future__ import annotations

from openai import OpenAI

from legal_data.config import get_settings


def build_openrouter_client() -> OpenAI:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY no está configurada en el entorno")

    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
