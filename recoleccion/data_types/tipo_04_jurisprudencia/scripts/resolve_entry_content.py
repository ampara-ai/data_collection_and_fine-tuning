#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup

from legal_data.paths import PROCESSED_DIR, RAW_DIR
from legal_data.storage import write_json

INPUT_JSON = PROCESSED_DIR / "jurisprudence_entries_deduped.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_entry_content.json"
RAW_HTML_DIR = RAW_DIR / "entry_detail_html_full"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _html_to_markdown_like(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.td-post-content") or soup.body or soup
    
    lines = []
    for tag in content.find_all(["h2", "h3", "h4", "p", "li", "strong", "a"], limit=260):
        text = " ".join(tag.get_text(" ", strip=True).split())
        if not text:
            continue
            
        if any(noise in text.lower() for noise in ["inscríbete aquí", "más información", "matricúlate", "diplomado"]):
            continue
            
        if tag.name == "a":
            href = tag.get("href")
            if href and href.endswith(".pdf"):
                lines.append(f"[pdf] {href}")
            continue
            
        lines.append(f"[{tag.name}] {text}")
        
    return "\n".join(lines)


def main() -> None:
    items = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    results = []
    
    print(f"Procesando {len(items)} archivos locales...")

    for item in items:
        entry_id = item.get("entry_id")
        
        # Armamos la ruta de donde debería estar el HTML guardado
        raw_path = RAW_HTML_DIR / f"{entry_id}.html"
        
        # Validamos que el archivo realmente exista en tu disco
        if not raw_path.is_file():
            results.append({
                **item, 
                "content_status": "error: local_html_not_found", 
                "detail_raw_html_path": str(raw_path), 
                "detail_text": None, 
                "detail_sha256": None, 
                "best_source_type": "none", 
                "combined_text": None
            })
            continue
            
        try:
            # Leemos el HTML desde el disco local
            html = raw_path.read_text(encoding="utf-8")
            
            # Lo procesamos con tu motor Híbrido a Markdown
            detail_markdown = _html_to_markdown_like(html)
            
            results.append({
                **item, 
                "content_status": "success", 
                "detail_raw_html_path": str(raw_path), 
                "detail_text": detail_markdown, 
                "detail_sha256": _sha256_text(html), 
                "best_source_type": "detail_html", 
                "combined_text": detail_markdown
            })
        except Exception as exc:
            results.append({
                **item, 
                "content_status": f"error: {exc}", 
                "detail_raw_html_path": str(raw_path), 
                "detail_text": None, 
                "detail_sha256": None, 
                "best_source_type": "none", 
                "combined_text": None
            })
            
    write_json(OUTPUT_JSON, results)
    
    print(json.dumps({
        "entries_total": len(results), 
        "resolved_success": sum(1 for x in results if x.get('content_status') == 'success'), 
        "not_found": sum(1 for x in results if x.get('content_status') == 'error: local_html_not_found'),
        "output_path": str(OUTPUT_JSON)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()