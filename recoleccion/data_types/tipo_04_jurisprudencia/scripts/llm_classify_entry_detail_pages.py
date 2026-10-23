#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_json

INPUT_JSON = PROCESSED_DIR / "jurisprudence_entry_detail_pages_10.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_entry_detail_classification_10.json"


class DetailClassificationModel(BaseModel):
    document_kind: str
    resolution_type: str | None
    court_level: str | None
    has_case_facts: bool
    has_procedural_background: bool
    is_doctrinal_only: bool
    relevance_status: str
    relevance_reason: str
    pdf_url: str | None
    notes: str


SYSTEM_PROMPT = """Eres un clasificador jurídico. Recibirás el contenido limpio de una publicación individual de LP Derecho. Debes decidir si el documento contiene un caso con hechos/antecedentes útiles para dataset jurídico orientado a casos reales, o si es doctrina/guía/criterio abstracto. Responde SOLO en JSON válido y no inventes datos."""


def classify_detail(client: OpenAI, model: str, item: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "entry_title_raw": item.get("entry_title_raw"),
        "entry_category": item.get("entry_category"),
        "detail_page_title": item.get("detail_page_title"),
        "detail_markdown": item.get("detail_markdown"),
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Clasifica este entry detail y responde SOLO con JSON válido.\n"
                "Usa `relevance_status` en {accepted, conditional, rejected}.\n"
                "accepted = caso con hechos/antecedentes útiles.\n"
                "rejected = doctrina, guía o material sin caso real útil.\n\n"
                f"PAYLOAD:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        extra_headers={
            "HTTP-Referer": "https://openclaw.local",
            "X-Title": os.environ.get("APP_NAME", "peru-legal-rag-data"),
        },
    )
    if not response.choices or not response.choices[0].message or not response.choices[0].message.content:
        raise RuntimeError(f"empty model response: {response}")
    parsed = json.loads(response.choices[0].message.content)
    return {**item, "detail_llm": parsed}


def main() -> None:
    load_dotenv()
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    model = os.environ.get("OPENROUTER_MODEL", "x-ai/grok-4.1-fast")

    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    outputs = []
    for item in items:
        if item.get("detail_fetch_status") != "success" or not item.get("detail_markdown"):
            outputs.append({**item, "detail_llm": None})
            continue
        try:
            print(f"classifying detail {item['entry_id']}", flush=True)
            outputs.append(classify_detail(client, model, item))
        except Exception as exc:
            outputs.append({**item, "detail_llm": {"relevance_status": "error", "relevance_reason": str(exc)}})

    write_json(OUTPUT_JSON, outputs)
    print(json.dumps({"classified": len(outputs), "output_path": str(OUTPUT_JSON)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
