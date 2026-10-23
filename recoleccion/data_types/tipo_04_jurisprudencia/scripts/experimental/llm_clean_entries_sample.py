#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

INPUT_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_entries_structured.json")
OUTPUT_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_entries_llm_sample.json")

SCHEMA = {
    "name": "jurisprudence_entry_cleanup",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "clean_title": {"type": "string"},
            "clean_summary": {"type": "string"},
            "normalized_resolution_reference": {"type": ["string", "null"]},
            "entry_type_refined": {
                "type": "string",
                "enum": ["jurisprudencia", "doctrina_legal", "legislacion", "otro"]
            },
            "domain_relevance": {
                "type": "string",
                "enum": ["high", "medium", "low", "none"]
            },
            "notes": {"type": "string"}
        },
        "required": [
            "clean_title",
            "clean_summary",
            "normalized_resolution_reference",
            "entry_type_refined",
            "domain_relevance",
            "notes"
        ],
        "additionalProperties": False
    }
}

SYSTEM_PROMPT = """Eres un asistente jurídico-técnico que limpia entries jurisprudenciales de LP Derecho para construir datasets de retrieval. Debes devolver JSON válido según el schema. No inventes hechos. Si el texto está roto o incompleto, sé conservador y dilo en notes."""


def build_messages(entry: dict) -> list[dict]:
    payload = {
        "entry_category": entry.get("entry_category"),
        "entry_type": entry.get("entry_type"),
        "entry_text": entry.get("entry_text"),
        "resolution_reference_raw": entry.get("resolution_reference_raw"),
        "page_anchor_article_id": entry.get("page_anchor_article_id"),
        "page_anchor_article_heading": entry.get("page_anchor_article_heading"),
        "page_concordances": entry.get("page_concordances"),
        "lp_entry_url": entry.get("lp_entry_url"),
    }
    user_prompt = (
        "Limpia este entry jurisprudencial.\n"
        "Objetivos:\n"
        "1. reconstruir un titulo limpio y breve,\n"
        "2. generar un resumen corto del criterio sin inventar,\n"
        "3. normalizar la referencia si es posible,\n"
        "4. refinar el tipo de entry,\n"
        "5. estimar relevancia para dominio de violencia familiar/genero en Peru.\n"
        "Si el texto esta truncado o incompleto, dilo en notes.\n\n"
        f"ENTRY:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def main() -> None:
    load_dotenv()
    entries = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    sample = [e for e in entries if e.get("lp_entry_url")][:1]

    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    model = os.environ.get("OPENROUTER_MODEL", "qwen/qwen3.5-plus-02-15")

    results = []
    for entry in sample:
        print(f"processing {entry['entry_id']}", flush=True)
        response = client.chat.completions.create(
            model=model,
            messages=build_messages(entry),
            response_format={"type": "json_schema", "json_schema": SCHEMA},
            extra_headers={
                "HTTP-Referer": "https://openclaw.local",
                "X-Title": os.environ.get("APP_NAME", "peru-legal-rag-data"),
            },
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        results.append({
            "entry_id": entry["entry_id"],
            "raw_entry_text": entry["entry_text"],
            "lp_entry_url": entry.get("lp_entry_url"),
            "llm_cleaned": parsed,
        })

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sample_size": len(results), "output_path": str(OUTPUT_PATH)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
