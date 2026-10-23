#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

PATH = Path("recoleccion/data_types/tipo_04_jurisprudencia/data/processed/jurisprudence_parsed_summary.json")


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
