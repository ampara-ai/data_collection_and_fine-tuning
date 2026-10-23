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

from legal_data.paths import PROCESSED_DIR
from legal_data.storage import write_json

INPUT_JSON = PROCESSED_DIR / "jurisprudence_index_pages.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_entries_raw.json"

SYSTEM_PROMPT = """Eres un extractor jurídico. Recibirás una página índice caótica de LP Derecho ya preprocesada. Debes identificar entries reales de jurisprudencia o documentos jurídicos relevantes enlazados en la página. Responde SOLO en JSON válido con la clave `entries`. Cada entry debe incluir: `title`, `matched_url`, `pdf_url`, `document_kind`, `why_relevant`, `confidence`. No inventes URLs. Usa solo URLs que aparezcan en el payload."""


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_clean_payload(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.td-post-content") or soup.body or soup
    lines = []
    urls = []
    anchors = []
    for tag in content.find_all(["h2", "h3", "li", "p", "strong", "a"], limit=500):
        txt = normalize_text(tag.get_text(" ", strip=True))
        if not txt:
            continue
        if any(noise in txt.lower() for noise in ["inscríbete aquí", "más información", "matricúlate", "diplomado", "whatsapp", "telegram"]):
            continue
        if tag.name == "a":
            href = tag.get("href")
            if href and "lpderecho.pe" in href:
                urls.append(href)
                anchors.append({"text": txt, "href": href})
            elif href and href.lower().endswith(".pdf"):
                urls.append(href)
                anchors.append({"text": txt, "href": href})
            continue
        lines.append(f"[{tag.name}] {txt}")
    seen = set()
    deduped_urls = []
    for u in urls:
        if u not in seen:
            deduped_urls.append(u)
            seen.add(u)
    return {"clean_text": "\n".join(lines[:300]), "urls": deduped_urls[:250], "anchors": anchors[:250]}


def parse_page(client: OpenAI, model: str, item: dict[str, Any]) -> dict[str, Any]:
    html = Path(item["raw_html_path"]).read_text(encoding="utf-8", errors="replace")
    payload = build_clean_payload(html)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        extra_headers={
            "HTTP-Referer": "https://openclaw.local",
            "X-Title": os.environ.get("APP_NAME", "peru-legal-rag-data"),
        },
    )
    content = response.choices[0].message.content if response.choices and response.choices[0].message else None
    if not content:
        raise RuntimeError("empty model response")
    parsed = json.loads(content)
    entries = []
    for counter, entry in enumerate(parsed.get("entries") or [], start=1):
        entries.append(
            {
                "entry_id": f"{item['index_page_id']}_e{counter:04d}",
                "index_page_id": item["index_page_id"],
                "index_page_url": item["index_page_url"],
                "index_page_title": item.get("title"),
                "entry_title_raw": entry.get("title"),
                "entry_url": entry.get("matched_url"),
                "pdf_url": entry.get("pdf_url"),
                "document_kind": entry.get("document_kind"),
                "why_relevant": entry.get("why_relevant"),
                "llm_confidence": entry.get("confidence"),
                "provenance_sources": item.get("provenance_sources", []),
            }
        )
    return {"index_page_id": item["index_page_id"], "parse_status": "success", "entries": entries}


def main() -> None:
    load_dotenv()
    client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    model = os.environ.get("OPENROUTER_MODEL", "x-ai/grok-4.1-fast")
    pages = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    outputs = []
    all_entries = []
    for item in pages:
        if item.get("fetch_status") != "ok" or not item.get("raw_html_path"):
            outputs.append({"index_page_id": item["index_page_id"], "parse_status": "skipped", "entries": []})
            continue
        try:
            result = parse_page(client, model, item)
            outputs.append(result)
            all_entries.extend(result["entries"])
        except Exception as exc:
            outputs.append({"index_page_id": item["index_page_id"], "parse_status": f"error: {exc}", "entries": []})
    write_json(OUTPUT_JSON, all_entries)
    print(json.dumps({"pages_total": len(pages), "entries_total": len(all_entries), "output_path": str(OUTPUT_JSON)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
