"""
Aplica las síntesis jurídicas generadas por el LLM a los chunks de jurisprudencia.

Lee jurisprudencia_chunk_updates.jsonl (generado por generate_colloquial_legal_questions.py)
y reemplaza el campo `text` de los chunks correspondientes en document_chunks_all.jsonl.

Actualiza:
  - recoleccion/data/processed/document_chunks_all.jsonl (fuente de verdad)
  - generacion_dataset/data/input/document_chunks_all.jsonl (copia)

Elimina el índice BM25 cacheado para forzar su reconstrucción en el próximo run.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent

UPDATES_JSONL = PROJECT_ROOT / "data" / "intermediate" / "jurisprudencia_chunk_updates.jsonl"
INPUT_CHUNKS = PROJECT_ROOT / "data" / "input" / "document_chunks_all.jsonl"
SOURCE_CHUNKS = REPO_ROOT / "recoleccion" / "data" / "processed" / "document_chunks_all.jsonl"


def load_updates(updates_path: Path) -> dict[str, str]:
    """Devuelve {chunk_id: new_text}."""
    updates: dict[str, str] = {}
    with updates_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            chunk_id = entry.get("chunk_id")
            new_text = entry.get("new_text", "").strip()
            if chunk_id and new_text:
                updates[chunk_id] = new_text
    return updates


def apply_updates_to_jsonl(source: Path, dest: Path, updates: dict[str, str]) -> tuple[int, int]:
    """
    Reescribe `source` en `dest` aplicando los updates.
    Retorna (total_chunks, updated_count).
    """
    total = 0
    updated = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")

    with source.open(encoding="utf-8") as fin, tmp.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            chunk_id = chunk.get("chunk_id")
            if chunk_id and chunk_id in updates:
                chunk["text"] = updates[chunk_id]
                updated += 1
            fout.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            total += 1

    tmp.replace(dest)
    return total, updated


def main() -> None:
    if not UPDATES_JSONL.exists():
        print(f"[ERROR] No se encontró el archivo de updates: {UPDATES_JSONL}")
        print("        Ejecuta primero generate_colloquial_legal_questions.py.")
        return

    print(f"[INFO] Leyendo updates de: {UPDATES_JSONL}")
    updates = load_updates(UPDATES_JSONL)
    print(f"[INFO] Chunks a actualizar: {len(updates)}")

    if not updates:
        print("[WARN] No hay updates que aplicar.")
        return

    # Aplicar sobre la fuente de verdad
    if SOURCE_CHUNKS.exists():
        total, updated = apply_updates_to_jsonl(SOURCE_CHUNKS, SOURCE_CHUNKS, updates)
        print(f"[OK] Fuente de verdad: {updated}/{total} chunks actualizados → {SOURCE_CHUNKS}")
    else:
        print(f"[WARN] No se encontró la fuente de verdad: {SOURCE_CHUNKS}")

    # Aplicar sobre la copia de input
    if INPUT_CHUNKS.exists():
        total, updated = apply_updates_to_jsonl(INPUT_CHUNKS, INPUT_CHUNKS, updates)
        print(f"[OK] Input copia: {updated}/{total} chunks actualizados → {INPUT_CHUNKS}")
    else:
        print(f"[WARN] No se encontró el input de generación: {INPUT_CHUNKS}")

    print("\n[DONE] Actualizaciones aplicadas.")
    print("       El generador reconstruirá el índice BM25 al iniciar.")


if __name__ == "__main__":
    main()
