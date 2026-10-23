#!/usr/bin/env python
"""Agrega al corpus los artículos del CP y del CPP que las sentencias citan (o enlazan) y que el filtro heurístico dejó fuera.

El resolutor de candidatos lee los códigos completos (all_articles.json), pero el corpus RAG solo tenía los artículos
que pasaron la heurística: ~46 % de los candidatos de los casos no existían en el corpus (art. 12, 29, 45, 92, 93, 177,
178 del CP; 429 del CPP...). Este script los genera con la MISMA función que usa el resolutor (article_to_chunk) y los escribe
en `document_chunks_cited.jsonl` de cada tipo; `recoleccion/scripts/consolidate_document_chunks.py` los une al corpus y les
aplica la misma limpieza que a los demás chunks.

Uso: python add_cited_articles.py            # recalcula y escribe (idempotente)
"""
import json
import sys
from collections import Counter
from pathlib import Path

import config
from common import load_corpus, read_json, write_jsonl

sys.path.insert(0, str(config.SCRIPTS_V1))
import generate_colloquial_legal_questions as v1                     # noqa: E402
from legal_candidate_resolver import LegalCandidateResolver, article_to_chunk, SOURCE_CP, SOURCE_CPP  # noqa: E402

# El corpus BASE (sin los artículos citados) es la concatenación cruda de los chunks de cada tipo.
base_ids = set()
for t in ("tipo_01_ley_30364", "tipo_02_codigo_penal", "tipo_03_codigo_procesal_penal", "tipo_04_jurisprudencia", "tipo_05_documentos_institucionales"):
    p = config.REPO / "recoleccion" / "data_types" / t / "data" / "processed" / "document_chunks.jsonl"
    if p.exists():
        base_ids |= {json.loads(l)["chunk_id"] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}

resolver = LegalCandidateResolver.from_paths(
    cp_articles_path=config.CP_ARTICLES_PATH, cpp_articles_path=config.CPP_ARTICLES_PATH, ley_30364_path=config.LEY_30364_PATH,
    context_units_path=config.CONTEXT_UNITS_PATH, structured_entries_path=config.STRUCTURED_ENTRIES_PATH)
merged = v1.merge_corpus_chunks(v1.load_chunks(config.CHUNKS_PATH), resolver.all_article_chunks())
lookup = v1.build_lookup_indexes(merged)

missing: dict[str, dict] = {}
cases = 0
for p in sorted(config.CASES_DIR.glob("*.json")):
    cd = read_json(p)
    if not (cd.get("factual_density_signals") or {}).get("is_dataset_candidate", True):
        continue
    cases += 1
    jc, _ = v1.resolve_case_jurisprudence(case_data=cd, lookup=lookup)
    for c in resolver.resolve_case(case_id=v1.get_case_id(p, cd), jurisprudence_chunks=jc).candidates:
        ch = c["chunk"]
        if c["candidate_id"] not in base_ids and ch.get("source_type") in (SOURCE_CP, SOURCE_CPP) and (ch.get("text") or "").strip():
            missing.setdefault(c["candidate_id"], ch)

by_type: dict[str, list] = {SOURCE_CP: [], SOURCE_CPP: []}
for cid in sorted(missing):
    by_type[missing[cid]["source_type"]].append(missing[cid])
dirs = {SOURCE_CP: "tipo_02_codigo_penal", SOURCE_CPP: "tipo_03_codigo_procesal_penal"}
for st, rows in by_type.items():
    out = config.REPO / "recoleccion" / "data_types" / dirs[st] / "data" / "processed" / "document_chunks_cited.jsonl"
    write_jsonl(out, rows)
    print(f"{st}: {len(rows)} artículos citados por las sentencias que faltaban -> {out.relative_to(config.REPO)}")
print(f"casos revisados: {cases} | artículos agregados: {len(missing)}")
