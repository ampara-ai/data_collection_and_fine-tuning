#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from legal_data.paths import PROJECT_ROOT, PROCESSED_DIR
from legal_data.storage import write_json

TIPO_02_ALL = PROJECT_ROOT / "recoleccion" / "data_types" / "tipo_02_codigo_penal" / "data" / "processed" / "candidate_articles.json"
TIPO_03_ALL = PROJECT_ROOT / "recoleccion" / "data_types" / "tipo_03_codigo_procesal_penal" / "data" / "processed" / "candidate_articles.json"
OUTPUT_JSON = PROCESSED_DIR / "jurisprudence_seed_urls.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/") + "/"


def _iter_rows(source_type: str, items: list[dict[str, Any]]):
    for item in items:
        url = item.get("jurisprudence_url")
        if not url:
            continue
        yield {
            "seed_url": _normalize_url(url),
            "source_type": source_type,
            "source_article_id": item.get("article_id"),
            "source_article_title": item.get("title") or item.get("heading"),
            "candidate_status": item.get("candidate_status"),
        }


def main() -> None:
    rows = list(_iter_rows("tipo_02_codigo_penal", _load(TIPO_02_ALL))) + list(_iter_rows("tipo_03_codigo_procesal_penal", _load(TIPO_03_ALL)))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["seed_url"]].append({k: v for k, v in row.items() if k != "seed_url"})

    output = []
    for idx, (seed_url, provenance) in enumerate(sorted(grouped.items()), start=1):
        output.append(
            {
                "seed_id": f"seed_{idx:05d}",
                "seed_url": seed_url,
                "provenance_sources": provenance,
                "provenance_count": len(provenance),
            }
        )

    write_json(OUTPUT_JSON, output)
    print(json.dumps({"seed_urls_total": len(output), "output_path": str(OUTPUT_JSON)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
