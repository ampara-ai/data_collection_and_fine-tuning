#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("recoleccion/data_types/tipo_02_codigo_penal/data/processed/candidate_articles.json")


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    data.sort(key=lambda x: (-x["heuristic_score"], x["article_id"]))
    for item in data[:25]:
        print(
            f"{item['article_id']:>6} | {item['candidate_status']:<17} | score={item['heuristic_score']:<3} | {item['heading'][:120]}"
        )


if __name__ == "__main__":
    main()
