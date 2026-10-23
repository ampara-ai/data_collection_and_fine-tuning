#!/usr/bin/env python
"""Paso 5: verificación independiente de los pares (pregunta, chunk).

El generador elige los positivos viendo los candidatos al escribir la pregunta (circularidad) y los negativos los
elige un algoritmo (pueden ser falsos negativos). Aquí un juez, sin saber qué rol tiene cada chunk, lee el texto
completo y dice si responde la pregunta (si / parcial / no).

Qué se juzga:
  * train: todos los positivos; y TODOS los negativos de una fracción NEG_JUDGE_FRACTION de las preguntas (muestra para
           estimar la tasa de falsos negativos); más los negativos "difíciles" del caso si CASE_CANDIDATE_NEGS > 0.
  * dev/test: el chunk de origen de cada pregunta (se descarta la pregunta si no es "si").
Los chunks se presentan en orden determinista mezclado (el juez no ve el rol).

ALMACÉN PERSISTENTE (para trabajar por olas): cada veredicto se guarda por par (dataset_id, chunk_id) en
judgments_store.jsonl. En cada ejecución: (1) se leen TODAS las respuestas que haya en work/05_judge/responses/ (cualquier
tarea, incluso antigua), (2) se calculan los pares que faltan y solo esos se piden, (3) judgments.jsonl queda con los
pares vigentes y su rol. Así una ola nueva no vuelve a juzgar lo que ya está juzgado aunque cambien los negativos.

Uso: python 05_judge.py --backend session
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import config
from common import check_freeze, load_corpus, read_jsonl, stable_unit, write_json, write_jsonl
from llm_backend import Backend, finish, run_tasks
from questions import load_prompt

ap = argparse.ArgumentParser()
ap.add_argument("--backend", default="session", choices=["openrouter", "session", "mock"])
ap.add_argument("--model", default=config.JUDGE_MODEL)
ap.add_argument("--chunks", default=str(config.CHUNKS_PATH))
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--neg-fraction", type=float, default=config.NEG_JUDGE_FRACTION,
                help="fracción de preguntas train cuyos negativos se juzgan todos (1.0 = todas)")
args = ap.parse_args()
out_dir = Path(args.out_dir).resolve()
check_freeze(out_dir, Path(args.chunks))

corpus = load_corpus(Path(args.chunks))
questions = []
for name in ("case_questions.jsonl", "chunk_questions_train.jsonl", "chunk_questions_dev.jsonl", "chunk_questions_test.jsonl"):
    p = out_dir / name
    if p.exists():
        questions += read_jsonl(p)
negs = {r["dataset_id"]: r for r in read_jsonl(out_dir / "negatives.jsonl")} if (out_dir / "negatives.jsonl").exists() else {}

# ---- pares necesarios y su rol
items = []
for q in sorted(questions, key=lambda q: q["dataset_id"]):
    pairs = {}
    if q["split"] == "train":
        for p in q["positive_chunk_ids"]:
            pairs[p] = "positive"
        n = negs.get(q["dataset_id"])
        if n is None:
            continue                                   # aún sin negativos (falta el paso 4)
        judge_all = stable_unit(config.SEED, "judge", q["dataset_id"]) < args.neg_fraction
        must = set(n["must_judge"])
        for c in n["negatives"]:
            if judge_all or c["chunk_id"] in must:
                pairs.setdefault(c["chunk_id"], "negative")
    else:
        pairs[q["positive_chunk_ids"][0]] = "origin"
    items.append({"dataset_id": q["dataset_id"], "question": q["query"], "pairs": pairs, "split": q["split"],
                  "origin": str(q.get("case_id") or q.get("origin_chunk_id"))})
role = {(i["dataset_id"], c): r for i in items for c, r in i["pairs"].items()}

# ---- almacén persistente + todas las respuestas existentes
store_path = out_dir / "judgments_store.jsonl"
store = {(r["dataset_id"], r["chunk_id"]): r for r in read_jsonl(store_path)} if store_path.exists() else {}
backend = Backend(args.backend, "05_judge", out_dir, args.model, config.JUDGE_TEMPERATURE,
                  mock_fn=lambda task_id, meta: {"judgments": [
                      {"dataset_id": d, "chunk_id": c, "relevance": "no" if r == "negative" else "si", "rationale": "mock"}
                      for (d, c), r in meta["roles"]]})


def ingest_responses() -> int:
    added = 0
    for p in sorted(backend.res_dir.glob("*.json")):
        try:
            resp = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for j in resp.get("judgments") or []:
            k = (j.get("dataset_id"), j.get("chunk_id"))
            if k[0] is None or k[1] is None or k in store or j.get("relevance") not in ("si", "parcial", "no"):
                continue
            store[k] = {"dataset_id": k[0], "chunk_id": k[1], "relevance": j["relevance"], "rationale": str(j.get("rationale") or ""),
                        "judge_model": str(resp.get("_model") or args.model), "task_id": p.stem}
            added += 1
    return added


def plan() -> list[dict]:
    """Tareas con los pares que faltan; lotes estables por hash del origen (caso/chunk)."""
    missing = [(i, c) for i in items for c in i["pairs"] if (i["dataset_id"], c) not in store]
    BUCKETS = {"train": 300, "eval": 60}
    groups: dict[tuple, dict] = {}
    for i, c in missing:
        g = "train" if i["split"] == "train" else "eval"
        b = (g, int(stable_unit(config.SEED, "judgebucket", i["origin"]) * BUCKETS[g]))
        groups.setdefault(b, {}).setdefault(i["dataset_id"], (i, []))[1].append(c)
    out = []
    system = load_prompt("judge_system.txt")
    for b in sorted(groups):
        batch = [groups[b][d] for d in sorted(groups[b])]
        key = "|".join(f"{i['dataset_id']}:{','.join(sorted(cs))}" for i, cs in batch)
        payload = [{"dataset_id": i["dataset_id"], "question": i["question"],
                    "chunks": [{"chunk_id": c, "title": corpus[c].get("title"), "text": corpus[c]["text"][: config.JUDGE_TEXT_CHARS]}
                               for c in sorted(cs, key=lambda c: stable_unit(config.SEED, i["dataset_id"], c))]} for i, cs in batch]
        out.append({"task_id": f"judge__{hashlib.sha1(key.encode()).hexdigest()[:12]}", "system": system,
                    "user": "Juzga estos pares:\n\n" + json.dumps(payload, ensure_ascii=False, indent=1),
                    "roles": [((i["dataset_id"], c), role[(i["dataset_id"], c)]) for i, cs in batch for c in cs]})
    return out


ingest_responses()
tasks = plan()
pending, errors = [], []
if args.backend in ("openrouter", "mock") and tasks:
    def handler(t):
        return backend.complete_json(t["task_id"], t["system"], t["user"], meta={"roles": t["roles"]})
    _, pending, errors = run_tasks(tasks, handler, backend, args.workers)
    ingest_responses()
    tasks = plan()                                     # lo que siga faltando (respuestas incompletas o inválidas)
    errors += [(t["task_id"], "respuesta incompleta o inválida") for t in tasks]
elif tasks:                                            # session: dejar SOLO las peticiones vigentes
    current = {t["task_id"] for t in tasks}
    for p in backend.req_dir.glob("*.json"):
        if p.stem not in current and not (backend.res_dir / p.name).exists():
            p.unlink()                                 # petición obsoleta (sus pares ya se juzgaron o cambiaron)
    for t in tasks:
        try:
            backend.complete_json(t["task_id"], t["system"], t["user"], meta={"roles": t["roles"]})
        except Exception:                              # PendingResponse: la petición queda escrita
            pass
    pending = [t["task_id"] for t in tasks]

write_jsonl(store_path, [store[k] for k in sorted(store)])
rows = [{**store[k], "role": role[k]} for k in sorted(store) if k in role]
write_jsonl(out_dir / "judgments.jsonl", rows)
by = Counter((r["role"], r["relevance"]) for r in rows)
summary = {f"{r}:{v}": n for (r, v), n in sorted(by.items())}
write_json(out_dir / "judgments_report.json", {"pares_necesarios": len(role), "pares_juzgados": len(rows),
                                               "pares_faltantes": len(role) - len(rows), "por_rol_y_veredicto": summary,
                                               "tareas_pendientes": len(pending)})
print(json.dumps({"pares_necesarios": len(role), "pares_juzgados": len(rows), "pares_faltantes": len(role) - len(rows), **summary},
                 ensure_ascii=False, indent=1))
finish("05_judge", backend, pending, errors)
