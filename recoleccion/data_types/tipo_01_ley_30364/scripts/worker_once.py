#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path

from legal_data.state import load_state, save_state


def main() -> None:
    state = load_state()
    now = datetime.now(UTC).isoformat()
    state["last_daily_check"] = now
    save_state(state)
    print(json.dumps({"status": "placeholder", "checked_at": now}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
