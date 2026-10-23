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

from legal_data.paths import PROCESSED_DIR

INPUT_JSON = PROCESSED_DIR / "input_indices_10.json"
OUTPUT_PATH = PROCESSED_DIR / "jurisprudence_index_llm_10.json"


class EntryModel(BaseModel):
    title: str
    matched_url: str | None


class CategoryModel(BaseModel):
    name: str
    entries: list[EntryModel]


class IndexPageModel(BaseModel):
    categories: list[CategoryModel]
    article: str
    concordancias: dict[str, str]
    notes: str


SYSTEM_PROMPT = """Eres un extractor jurídico. Debes responder SOLO en JSON válido. Recibirás el texto limpio de una página índice de jurisprudencia de LP Derecho y una lista de URLs reales detectadas en esa página. Debes reconstruir las categorías y sus entries sin inventar. Usa matched_url solo si coincide claramente con una URL real de la lista. Prioriza fidelidad estructural sobre creatividad."""


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_clean_payload(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.td-post-content")
    if not content:
        raise RuntimeError("td-post-content not found")

    lines = []
    urls = []
    for tag in content.find_all(["h2", "h3", "li", "p", "strong", "a"]):
        txt = normalize_text(tag.get_text(" ", strip=True))
        if not txt:
            continue
        if any(noise in txt.lower() for noise in ["inscríbete aquí", "más información", "matricúlate", "diplomado", "email protected"]):
            continue
        if tag.name == "a":
            href = tag.get("href")
            if href and "lpderecho.pe" in href:
                urls.append(href)
            continue
        lines.append(f"[{tag.name}] {txt}")

    seen = set()
    deduped_urls = []
    for u in urls:
        if u not in seen:
            deduped_urls.append(u)
            seen.add(u)

    return {
        "clean_text": "\n".join(lines),
        "urls": deduped_urls,
    }


def extract_page(client: OpenAI, model: str, item: dict[str, Any]) -> dict[str, Any]:
    html = Path(item["raw_html_path"]).read_text(encoding="utf-8", errors="replace")
    payload = build_clean_payload(html)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Extrae la estructura de esta página índice de jurisprudencia y responde en JSON válido.\n"
                "Devuelve categorías y entries.\n"
                "No inventes entries.\n"
                "No repitas duplicados obvios.\n"
                "Usa solo URLs de la lista dada cuando correspondan.\n\n"
                f"PAYLOAD:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
            ),
        },
    ]

    print(f"sending index page {item['index_page_id']}", flush=True)
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
    return {
        "index_page_id": item["index_page_id"],
        "index_page_url": item["index_page_url"],
        "article_id": item.get("article_id"),
        "article_heading": item.get("article_heading"),
        "llm_parse_status": "success",
        "parsed": parsed,
    }


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
        try:
            outputs.append(extract_page(client, model, item))
        except Exception as exc:
            outputs.append(
                {
                    "index_page_id": item["index_page_id"],
                    "index_page_url": item["index_page_url"],
                    "article_id": item.get("article_id"),
                    "article_heading": item.get("article_heading"),
                    "llm_parse_status": f"error: {exc}",
                    "parsed": None,
                }
            )

    OUTPUT_PATH.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_path": str(OUTPUT_PATH), "pages": len(outputs)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
