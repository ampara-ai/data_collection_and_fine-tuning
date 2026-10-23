#!/usr/bin/env python
"""Paso 3: preguntas basadas en CHUNKS, para cubrir todo el corpus y construir el set de evaluación.

Genera, para cada chunk de la partición pedida (train, dev, test), preguntas coloquiales con instrucciones
explícitas de anti-solapamiento léxico (la reformulación del set unseen ya va integrada en la generación).
Los chunks de dev/test jamás se usan para entrenar; sus preguntas son el set de evaluación.

* Se genera una vez por grupo de chunks idénticos/casi idénticos; todos los miembros del grupo son positivos.
* Un chunk puede omitirse (skip) si ninguna víctima lo preguntaría; queda registrado con su motivo.

OLAS Y ALMACÉN POR CHUNK: cada ola es una fracción acumulada (`--fraction`) de un orden aleatorio estable de los chunks de
cada partición. Los resultados se guardan por chunk (se leen TODAS las respuestas de work/03_chunk_questions/responses/,
sea cual sea la tarea que las produjo): si el corpus crece o los lotes cambian, lo ya respondido se reutiliza y solo se
piden los chunks que faltan.

Uso: python 03_chunk_questions.py --backend session --fraction 0.5
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import config
from common import check_freeze, load_corpus, read_json, stable_unit, write_json, write_jsonl
from llm_backend import Backend, finish, run_tasks
from questions import Deduper, check_question, load_prompt

ap = argparse.ArgumentParser()
ap.add_argument("--backend", default="session", choices=["openrouter", "session", "mock"])
ap.add_argument("--model", default=config.GENERATOR_MODEL)
ap.add_argument("--chunks", default=str(config.CHUNKS_PATH))
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
ap.add_argument("--splits", nargs="+", default=["train", "dev", "test"], choices=["train", "dev", "test"])
ap.add_argument("--limit-chunks", type=int, default=None, help="solo N chunks por partición, repartidos de forma pareja (pruebas)")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--max-overlap", type=float, default=config.MAX_LEXICAL_OVERLAP)
ap.add_argument("--chunks-per-task", type=int, default=config.CHUNKS_PER_TASK)
ap.add_argument("--fraction", type=float, default=1.0,
                help="fracción ACUMULADA (0-1) de los chunks de cada partición; prefijo de un orden estable: las olas se anidan")
args = ap.parse_args()
out_dir = Path(args.out_dir).resolve()
check_freeze(out_dir, Path(args.chunks))

corpus = load_corpus(Path(args.chunks))
sp = read_json(out_dir / "chunk_split.json")
assign, dup_groups = sp["assignments"], sp.get("duplicate_groups", [])
group_of = {cid: g for g in dup_groups for cid in g}

def mock_fn(task_id: str, meta: dict) -> dict:
    return {"results": [{"chunk_id": cid, "skip": False, "skip_reason": "",
                         "questions": [{"query": "Pregunta de prueba " + " ".join(f"termino{abs(hash(cid)) % 10**6}x{k}y{j}" for j in range(8)),
                                        "topic": "otro", "barrier": "otro", "expected_answer_focus": "mock"}
                                       for k in range(meta["K"])]} for cid in meta["chunk_ids"]]}


backend = Backend(args.backend, "03_chunk_questions", out_dir, args.model, config.GEN_TEMPERATURE, mock_fn=mock_fn)

# ---- almacén por chunk: todas las respuestas que existan, de cualquier tarea
store: dict[str, dict] = {}


def ingest_responses() -> None:
    for p in sorted(backend.res_dir.glob("*.json")):
        try:
            resp = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for r in resp.get("results") or []:
            cid = str(r.get("chunk_id"))
            if cid in assign and cid not in store:
                store[cid] = {"r": r, "model": str(resp.get("_model") or args.model)}


# ---- chunks seleccionados por partición (orden estable + prefijo)
report: Counter = Counter()
selected: dict[str, list[str]] = {}
for split in args.splits:
    reps = []
    for cid in sorted(c for c, s in assign.items() if s == split):
        g = group_of.get(cid)
        if g and cid != g[0]:
            continue                                  # un representante por grupo de duplicados
        reps.append(cid)
    if args.limit_chunks:                              # muestra repartida de forma pareja (solo para pruebas)
        reps = reps[:: max(1, len(reps) // args.limit_chunks)][: args.limit_chunks]
    else:                                              # orden aleatorio ESTABLE (no depende del tamaño del corpus)
        reps = sorted(reps, key=lambda c: stable_unit(config.SEED, "chunk_order", split, c))
        reps = reps[: math.ceil(args.fraction * len(reps))]
    selected[split] = reps
    report[f"chunks_{split}"] = len(reps)


def plan() -> list[dict]:
    tasks = []
    for split, reps in selected.items():
        K = config.CHUNK_QUESTIONS[split]
        system = load_prompt("chunk_system.txt", K=K)
        pend = [c for c in reps if c not in store]
        for i in range(0, len(pend), args.chunks_per_task):
            ids = pend[i: i + args.chunks_per_task]
            listing = [{"chunk_id": cid, "source_type": corpus[cid].get("source_type"), "title": corpus[cid].get("title"),
                        "text": corpus[cid]["text"]} for cid in ids]
            user = load_prompt("chunk_user.txt", N=len(ids), K=K, CHUNKS=json.dumps(listing, ensure_ascii=False, indent=1))
            tid = f"chunks__{split}__{hashlib.sha1('|'.join(ids).encode()).hexdigest()[:10]}"
            tasks.append({"task_id": tid, "split": split, "K": K, "chunk_ids": ids, "system": system, "user": user})
    return tasks


ingest_responses()
tasks = plan()
pending, errors = [], []
if args.backend in ("openrouter", "mock") and tasks:
    def handler(t):
        return backend.complete_json(t["task_id"], t["system"], t["user"], meta={"K": t["K"], "chunk_ids": t["chunk_ids"]})
    _, pending, errors = run_tasks(tasks, handler, backend, args.workers)
    ingest_responses()
    tasks = plan()
    errors += [(t["task_id"], "respuesta incompleta o inválida") for t in tasks]
elif tasks:                                            # session: dejar SOLO las peticiones vigentes
    current = {t["task_id"] for t in tasks}
    for p in backend.req_dir.glob("*.json"):
        if p.stem not in current and not (backend.res_dir / p.name).exists():
            p.unlink()
    for t in tasks:
        try:
            backend.complete_json(t["task_id"], t["system"], t["user"], meta={"K": t["K"], "chunk_ids": t["chunk_ids"]})
        except Exception:                              # PendingResponse: la petición queda escrita
            pass
    pending = [t["task_id"] for t in tasks]

# ---- preguntas y omisiones a partir del almacén (orden determinista por chunk)
dedupe = Deduper()
by_split: dict[str, list] = {s: [] for s in args.splits}
skipped = []
for cid in sorted(store):
    split = assign[cid]
    if split not in by_split:
        continue
    r, model = store[cid]["r"], store[cid]["model"]
    if r.get("skip"):
        skipped.append({"chunk_id": cid, "split": split, "reason": str(r.get("skip_reason") or "")})
        continue
    group = group_of.get(cid, [cid])
    K = config.CHUNK_QUESTIONS[split]
    n = 0
    for raw in (r.get("questions") or [])[:K]:
        q, why = check_question(raw, [corpus[g]["text"] for g in group], dedupe, args.max_overlap)
        if q is None:
            report[f"rechazada_{why}"] += 1
            continue
        n += 1
        by_split[split].append({
            "dataset_id": f"{split}::{cid}::q{n:02d}", "source": "chunk", "split": split,
            "case_id": None, "origin_chunk_id": cid, **q, "positive_chunk_ids": list(group),
            "generator_model": model, "prompt_version": config.PROMPT_VERSION, "backend": args.backend})
    report[f"chunks_con_preguntas_{split}"] += int(n > 0)

for s, rows in by_split.items():
    write_jsonl(out_dir / f"chunk_questions_{s}.jsonl", rows)
    report[f"preguntas_{s}"] = len(rows)
write_jsonl(out_dir / "chunk_questions_skipped.jsonl", skipped)
report["chunks_respondidos_en_almacen"] = len(store)
write_json(out_dir / "chunk_questions_report.json", dict(report))
print(json.dumps(dict(report), ensure_ascii=False, indent=1))
finish("03_chunk_questions", backend, pending, errors)
