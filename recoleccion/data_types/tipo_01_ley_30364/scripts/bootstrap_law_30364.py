#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from legal_data.renderers import render_law_markdown
from legal_data.spij_client import SpijClient
from legal_data.spij_parser import parse_spij_detail_to_law
from legal_data.state import load_state, save_state
from legal_data.storage import write_json, write_text


def main() -> None:
    state = load_state()
    target_json = Path("data/processed/ley_30364/current/articles.json")
    target_md = Path("data/processed/ley_30364/current/consolidated.md")

    if target_json.exists() and target_md.exists():
        print("Bootstrap ya existe. No se rehace.")
        return

    client = SpijClient()
    detail = client.get_norm_detail("H1141065")
    law = parse_spij_detail_to_law(detail)

    write_json(target_json, law.to_dict())
    write_text(target_md, render_law_markdown(law))

    state["bootstrap_done"] = True
    save_state(state)
    print(f"Bootstrap completado con {len(law.articles)} artículos parseados.")


if __name__ == "__main__":
    main()
