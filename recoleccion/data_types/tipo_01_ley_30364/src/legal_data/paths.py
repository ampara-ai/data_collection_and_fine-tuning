from __future__ import annotations

from pathlib import Path

TYPE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = TYPE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SCRIPTS_DIR = TYPE_DIR / "scripts"
