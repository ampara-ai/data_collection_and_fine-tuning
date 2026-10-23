from __future__ import annotations

from pathlib import Path

TYPE_04_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = TYPE_04_DIR.parents[2]
DATA_DIR = TYPE_04_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SCRIPTS_DIR = TYPE_04_DIR / "scripts"

TIPO_02_CANDIDATES = PROJECT_ROOT / "recoleccion" / "data_types" / "tipo_02_codigo_penal" / "data" / "processed" / "candidate_articles.json"
TIPO_03_CANDIDATES = PROJECT_ROOT / "recoleccion" / "data_types" / "tipo_03_codigo_procesal_penal" / "data" / "processed" / "candidate_articles.json"
