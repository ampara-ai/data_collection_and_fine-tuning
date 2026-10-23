#!/usr/bin/env python
"""Paso 2: preguntas basadas en CASOS (resumen de sentencia + candidatos cerrados), solo con chunks de TRAIN.

Cambios respecto de generate_colloquial_legal_questions.py (v1):
  * Los candidatos se restringen a chunks de la partición train; los de dev/test nunca llegan al LLM.
  * Los textos mostrados son los del corpus (document_chunks_all), idénticos a lo que se indexa en Mongo.
  * El LLM ya no elige negativos (los elige el paso 4, del mismo tipo de fuente, y los verifica el paso 5)
    ni sintetiza el texto de jurisprudencia (el corpus ya lo trae).
  * Instrucciones de anti-solapamiento léxico, variedad de candidatos y prioridad a normas poco cubiertas.
  * Filtros: solapamiento léxico con el positivo, citas de normas, duplicados.

Backends: --backend openrouter | session | mock   (ver llm_backend.py).
Uso: python 02_case_questions.py --backend session [--limit N] [--out-dir DIR]
"""
import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import config
from common import check_freeze, append_jsonl, load_corpus, read_json, stable_unit, write_json, write_jsonl
from llm_backend import Backend, finish, run_tasks
from questions import Deduper, check_question, load_prompt

ap = argparse.ArgumentParser()
ap.add_argument("--backend", default="session", choices=["openrouter", "session", "mock"])
ap.add_argument("--model", default=config.GENERATOR_MODEL)
ap.add_argument("--chunks", default=str(config.CHUNKS_PATH))
ap.add_argument("--cases-dir", default=str(config.CASES_DIR))
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
ap.add_argument("--limit", type=int, default=None)
ap.add_argument("--fraction", type=float, default=1.0,
                help="fracción ACUMULADA de casos a procesar (0-1). Es un prefijo de un orden aleatorio estable: la ola de 0.2 está "
                     "contenida en la de 0.5 y las tareas ya hechas se reutilizan")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--max-overlap", type=float, default=config.MAX_LEXICAL_OVERLAP)
ap.add_argument("--min-q", type=int, default=config.CASE_QUESTIONS_MIN)
ap.add_argument("--max-q", type=int, default=config.CASE_QUESTIONS_MAX)
args = ap.parse_args()
out_dir = Path(args.out_dir)
check_freeze(out_dir, Path(args.chunks))

sys.path.insert(0, str(config.SCRIPTS_V1))
import generate_colloquial_legal_questions as v1                      # noqa: E402  (reutiliza helpers del pipeline v1)
from legal_candidate_resolver import LegalCandidateResolver, candidates_for_prompt  # noqa: E402

corpus = load_corpus(Path(args.chunks))
split = read_json(out_dir / "chunk_split.json")["assignments"]

resolver = LegalCandidateResolver.from_paths(
    cp_articles_path=config.CP_ARTICLES_PATH, cpp_articles_path=config.CPP_ARTICLES_PATH,
    ley_30364_path=config.LEY_30364_PATH, context_units_path=config.CONTEXT_UNITS_PATH,
    structured_entries_path=config.STRUCTURED_ENTRIES_PATH)
merged = v1.merge_corpus_chunks(v1.load_chunks(Path(args.chunks)), resolver.all_article_chunks())
lookup = v1.build_lookup_indexes(merged)

RELATION_PRIORITY = {"case_jurisprudence": 0, "source_article_anchor": 1, "cited_in_jurisprudence": 2, "page_concordance": 3}
system = load_prompt("case_system.txt")

tasks, report = [], Counter()
for case_path in sorted(Path(args.cases_dir).glob("*.json"))[: args.limit]:
    case_data = read_json(case_path)
    if not (case_data.get("factual_density_signals") or {}).get("is_dataset_candidate", True):
        report["caso_no_candidato"] += 1
        continue
    case_id = v1.get_case_id(case_path, case_data)
    jchunks, _ = v1.resolve_case_jurisprudence(case_data=case_data, lookup=lookup)
    result = resolver.resolve_case(case_id=case_id, jurisprudence_chunks=jchunks)

    # Fuga a evitar: si la sentencia del caso es un chunk de dev/test, el resumen del caso (que usaríamos para
    # escribir preguntas de entrenamiento) describe el mismo contenido que se evalúa. Se omite el caso completo.
    jur_ids = [c["candidate_id"] for c in result.candidates
               if any(r["relation_type"] == "case_jurisprudence" for r in c["relations"])]
    if any(split.get(j) in ("dev", "test") for j in jur_ids):
        report["caso_omitido_su_sentencia_esta_en_dev_o_test"] += 1
        continue

    docs = []
    for cand in result.candidates:
        cid = cand["candidate_id"]
        if cid not in corpus:
            report["candidato_fuera_del_corpus"] += 1
            continue
        if split.get(cid) != "train":
            report[f"candidato_descartado_{split.get(cid, 'excluido')}"] += 1
            continue
        rel = [r["relation_type"] for r in cand["relations"]]
        docs.append((min(RELATION_PRIORITY.get(r, 9) for r in rel), cid, rel))
    docs.sort()
    docs = docs[: config.CASE_MAX_CANDIDATES]
    if not docs:
        report["caso_sin_candidatos_train"] += 1
        continue

    candidate_documents = []
    for _, cid, rel in docs:
        c = corpus[cid]
        candidate_documents.append({"candidate_id": cid, "source_type": c.get("source_type"), "title": c.get("title"),
                                    "article_id": (c.get("metadata") or {}).get("article_id"),
                                    "relation_types": rel, "text": c["text"]})
    payload = v1.extract_case_payload_for_llm(case_data)
    payload["temporal_notice"] = {"legal_text_basis": "current_repository_snapshot",
                                  "case_reference_year": v1.extract_case_reference_year(case_data)}
    payload["candidate_documents"] = candidate_documents
    user = load_prompt("case_user.txt", MIN_Q=args.min_q, MAX_Q=args.max_q,
                       PAYLOAD=json.dumps(payload, ensure_ascii=False, indent=1))
    tasks.append({"task_id": "case__" + re.sub(r"[^A-Za-z0-9_.-]", "_", case_id), "case_id": case_id, "user": user,
                  "candidate_ids": [d["candidate_id"] for d in candidate_documents], "case_data": case_data})

# Ola: prefijo de un orden determinista (no depende de la fracción ni de lo ya generado)
tasks.sort(key=lambda t: stable_unit(config.SEED, "case_order", t["case_id"]))
report["casos_elegibles"] = len(tasks)
tasks = tasks[: math.ceil(args.fraction * len(tasks))]
report["casos_en_esta_ola"] = len(tasks)


def mock_fn(task_id: str, meta: dict) -> dict:           # solo para probar el flujo
    ids = meta["candidate_ids"]
    tag = abs(hash(task_id)) % 10**6
    return {"questions": [{"query": "Pregunta de prueba " + " ".join(f"termino{tag}x{k}y{j}" for j in range(8)),
                           "topic": "otro", "barrier": "otro", "positive_candidate_ids": [ids[k % len(ids)]],
                           "positive_selection_reason": "mock", "expected_answer_focus": "mock",
                           "victim_voice_rationale": "mock"} for k in range(4)]}


backend = Backend(args.backend, "02_case_questions", out_dir, args.model, config.GEN_TEMPERATURE, mock_fn=mock_fn)


def handler(t):
    return t, backend.complete_json(t["task_id"], system, t["user"], meta={"candidate_ids": t["candidate_ids"]})


done, pending, errors = run_tasks(tasks, handler, backend, args.workers)
dedupe, rows = Deduper(), []
for t, resp in sorted(done, key=lambda x: x[0]["task_id"]):
    cand_ids = set(t["candidate_ids"])
    n = 0
    for raw in (resp.get("questions") or []):
        pos = list(dict.fromkeys(str(x) for x in (raw.get("positive_candidate_ids") or [])))
        if not pos or not set(pos) <= cand_ids:
            report["rechazada_ids_invalidos"] += 1
            continue
        q, why = check_question(raw, [corpus[p]["text"] for p in pos], dedupe, args.max_overlap)
        if q is None:
            report[f"rechazada_{why}"] += 1
            continue
        n += 1
        rows.append({
            "dataset_id": f"case::{t['case_id']}::q{n:02d}", "source": "case", "split": "train", "case_id": t["case_id"],
            **q, "positive_chunk_ids": pos, "candidate_chunk_ids": sorted(cand_ids),
            "positive_selection_reason": str(raw.get("positive_selection_reason") or ""),
            "victim_voice_rationale": str(raw.get("victim_voice_rationale") or ""),
            "generator_model": str(resp.get("_model") or args.model), "prompt_version": config.PROMPT_VERSION,
            "backend": args.backend})
    report["casos_con_preguntas"] += int(n > 0)

write_jsonl(out_dir / "case_questions.jsonl", rows)
report.update({"casos_procesados": len(done), "preguntas_aceptadas": len(rows)})
write_json(out_dir / "case_questions_report.json", dict(report))
print(json.dumps(dict(report), ensure_ascii=False, indent=1))
finish("02_case_questions", backend, pending, errors)
