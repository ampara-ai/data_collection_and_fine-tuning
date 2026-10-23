#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_entries_llm_sample.json")


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    for item in data:
        print(json.dumps(item, ensure_ascii=False, indent=2))
        print("\n" + "-" * 80 + "\n")


if __name__ == "__main__":
    main()
