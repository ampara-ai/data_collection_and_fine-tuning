#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

INPUT_URLS = [
    "https://lpderecho.pe/vigilancia-electronica-personal-acuerdo-plenario-02-2019-cij-116/",
    "https://lpderecho.pe/declaracion-nulidad-traslado-acusacion-suspende-inicio-control-acusacion-retrotrae-proceso-etapa-investigacion-preparatoria-apelacion-102-2024-corte-sup/",
    "https://lpderecho.pe/tercero-civil-marco-convenios-cooperacion-pnp-empresas-privadas-casacion-49-2020-apurimac/"
]
OUTPUT_PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_case_detail_llm_sample.json")


class CaseDetailModel(BaseModel):
    title: str
    highlighted_holding: str | None
    sumilla: str | None
    court: str | None
    resolution_reference: str | None
    facts_or_background: str | None
    legal_issue: str | None
    pdf_url: str | None
    notes: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch_clean_case_payload(url: str) -> dict[str, Any]:
    import requests
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    content = soup.select_one("div.td-post-content")
    if not content:
        raise RuntimeError("td-post-content not found")

    lines = []
    pdf_url = None
    for tag in content.find_all(["h2", "h3", "h4", "p", "strong", "a"], limit=220):
        txt = normalize_text(tag.get_text(" ", strip=True))
        if not txt:
            continue
        if any(noise in txt.lower() for noise in ["inscríbete aquí", "más información", "matricúlate", "diplomado"]):
            continue
        if tag.name == "a":
            href = tag.get("href")
            if href and href.endswith('.pdf'):
                pdf_url = href
            continue
        lines.append(f"[{tag.name}] {txt}")

    return {
        "url": url,
        "pdf_url_detected": pdf_url,
        "clean_text": "\n".join(lines),
    }


def main() -> None:
    load_dotenv()
    client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )
    model = os.environ.get("OPENROUTER_MODEL", "x-ai/grok-4.1-fast")

    results = []
    for url in INPUT_URLS:
        payload = fetch_clean_case_payload(url)
        messages = [
            {"role": "system", "content": "Eres un extractor jurídico. Responde SOLO en JSON válido. Extrae los campos principales de una publicación de jurisprudencia de LP Derecho sin inventar datos."},
            {"role": "user", "content": f"Extrae un resumen estructurado de esta resolución y responde en JSON válido.\n\nPAYLOAD:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"},
        ]
        print(f"processing case url {url}", flush=True)
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
        results.append({"url": url, "parsed": parsed})

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(OUTPUT_PATH), "cases": len(results)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
