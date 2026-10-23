from __future__ import annotations

from pathlib import Path
from typing import Any

from legal_data.storage import write_json


STATE_PATH = Path("data/state/worker_state.json")


def default_state() -> dict[str, Any]:
    return {
        "bootstrap_done": False,
        "last_daily_check": None,
        "law_snapshot_norm_id": "H1141065",
        "current_articles_path": "data/processed/ley_30364/current/articles.json",
        "current_markdown_path": "data/processed/ley_30364/current/consolidated.md",
        "change_log_path": "data/processed/ley_30364/change_log.jsonl",
        "related_updates_path": "data/processed/ley_30364/related_updates.json",
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        state = default_state()
        write_json(STATE_PATH, state)
        return state
    import json

    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    write_json(STATE_PATH, state)
