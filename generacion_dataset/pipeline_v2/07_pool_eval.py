#!/usr/bin/env python
"""Paso 7: completa por POOLING los qrels de dev y test (mismo procedimiento que el set unseen de quantitative_experiments).

Los qrels de 06 solo marcan el chunk de origen (y sus duplicados) como relevante; otros chunks que también responden la
pregunta cuentan como error para todos los sistemas y el recall queda como cota inferior. El pooling junta los top-k de
todos los sistemas que se comparan y un juez decide la relevancia de cada par (pregunta, chunk).

  export  Arma el pool y deja una petición por tarea (mismo formato que el paso 05; lo resuelve Codex/Claude/API).
            python 07_pool_eval.py export --split test --runs runs/*.json --depth 10
  ingest  Convierte las respuestas del juez (campo "_model" incluido) a la caché de juicios, construye los qrels
          ampliados y la muestra de verificación humana.
            python 07_pool_eval.py ingest --split test

Los runs son JSON {dataset_id: [chunk_id ordenados]} por sistema (backend/quantitative_experiments/ablation/build_runs.py).
Salidas en <out-dir>:
  pool_pairs_<split>.jsonl            pares del pool y qué sistemas los recuperaron (el juez NO lo ve)
  pool_judgments_<split>.jsonl        caché {qid, chunk_id, relevance, rationale, judge_model} (formato de
                                      quantitative_experiments/unseen_dataset/05_pool_qrels.py)
  eval_<split>_qrels_pooled.jsonl     origen + "si" (principal)
  eval_<split>_qrels_pooled_parcial.jsonl  origen + "si" + "parcial" (sensibilidad)
  human_review_pool_<split>.csv       muestra estratificada de juicios para la verificación humana (la única del proceso)
"""
import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

import config
from common import check_freeze, load_corpus, read_json, read_jsonl, stable_unit, write_json, write_jsonl
from llm_backend import Backend, PendingResponse
from questions import load_prompt

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["export", "ingest"])
ap.add_argument("--split", required=True, choices=["dev", "test"])
ap.add_argument("--runs", nargs="*", default=[], help="export: rankings por sistema (JSON {qid: [chunk_ids]})")
ap.add_argument("--depth", type=int, default=10, help="export: top-k de cada sistema que entra al pool")
ap.add_argument("--per-task", type=int, default=3, help="export: preguntas por tarea")
ap.add_argument("--human-sample", type=int, default=60)
ap.add_argument("--chunks", default=str(config.CHUNKS_PATH))
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
args = ap.parse_args()
out_dir = Path(args.out_dir).resolve()
check_freeze(out_dir, Path(args.chunks))

split = args.split
step = f"07_pool_{split}"
corpus = load_corpus(Path(args.chunks))
eval_rows = read_jsonl(out_dir / f"eval_{split}_dataset.jsonl")
origin = {r["dataset_id"]: set(r["positive_chunk_ids"]) for r in eval_rows}
question = {r["dataset_id"]: r["query"] for r in eval_rows}
cache_path = out_dir / f"pool_judgments_{split}.jsonl"
cache = {(r["qid"], r["chunk_id"]): r for r in read_jsonl(cache_path)} if cache_path.exists() else {}
tasks_path = out_dir / "work" / step / "tasks.json"
backend = Backend("session", step, out_dir, config.JUDGE_MODEL)

# ---------------------------------------------------------------- export
if args.mode == "export":
    if not args.runs:
        sys.exit("export necesita --runs")
    pool: dict[str, dict[str, list[str]]] = {}
    for rp in args.runs:
        name = Path(rp).stem
        for qid, ranked in read_json(Path(rp)).items():
            if qid not in origin:
                continue
            for cid in ranked[: args.depth]:
                if cid in corpus and cid not in origin[qid]:
                    pool.setdefault(qid, {}).setdefault(cid, []).append(name)
    pairs = [(q, c) for q in sorted(pool) for c in sorted(pool[q])]
    write_jsonl(out_dir / f"pool_pairs_{split}.jsonl", [{"qid": q, "chunk_id": c, "systems": sorted(pool[q][c])} for q, c in pairs])
    todo = {q: [c for c in sorted(pool[q]) if (q, c) not in cache] for q in sorted(pool)}
    todo = {q: cs for q, cs in todo.items() if cs}
    system = load_prompt("judge_system.txt")
    qids = sorted(todo)
    manifest = {}
    for i in range(0, len(qids), args.per_task):
        batch = qids[i: i + args.per_task]
        key = "|".join(f"{q}:{','.join(todo[q])}" for q in batch)
        task_id = f"pool_{split}__{hashlib.sha1(key.encode()).hexdigest()[:12]}"
        payload = []
        for q in batch:
            order = sorted(todo[q], key=lambda c: stable_unit(config.SEED, "pool", q, c))   # orden mezclado, sin rol ni sistema
            payload.append({"dataset_id": q, "question": question[q],
                            "chunks": [{"chunk_id": c, "title": corpus[c].get("title"),
                                        "text": corpus[c]["text"][: config.JUDGE_TEXT_CHARS]} for c in order]})
        user = "Juzga estos pares:\n\n" + json.dumps(payload, ensure_ascii=False, indent=1)
        manifest[task_id] = [[q, c] for q in batch for c in todo[q]]
        try:
            backend.complete_json(task_id, system, user, meta={})
        except PendingResponse:
            pass
    write_json(tasks_path, manifest)
    n_new = sum(len(v) for v in todo.values())
    print(f"[{step}] pool: {len(pairs)} pares ({len(pool)} preguntas, prof. {args.depth}, {len(args.runs)} sistemas) | "
          f"ya juzgados: {len(pairs) - n_new} | por juzgar: {n_new} en {len(manifest)} tareas")
    print(f"   peticiones: {backend.req_dir}\n   reparte con: python pending_tasks.py --out-dir {out_dir} --step {step} --shard K/N")
    sys.exit(0)

# ---------------------------------------------------------------- ingest
manifest = read_json(tasks_path)
new, pending, bad = 0, 0, []
for task_id, pairs in manifest.items():
    res_path = backend.res_dir / f"{task_id}.json"
    if not res_path.exists():
        pending += 1
        continue
    resp = read_json(res_path)
    got = {(j["dataset_id"], j["chunk_id"]): j for j in resp.get("judgments") or []}
    missing = [(q, c) for q, c in pairs if (q, c) not in got]
    invalid = [k for k, j in got.items() if j.get("relevance") not in ("si", "parcial", "no")]
    if missing or invalid:
        bad.append((task_id, len(missing), len(invalid)))
        continue
    for q, c in pairs:
        j = got[(q, c)]
        cache[(q, c)] = {"qid": q, "chunk_id": c, "relevance": j["relevance"], "rationale": str(j.get("rationale") or ""),
                         "judge_model": str(resp.get("_model") or config.JUDGE_MODEL), "task_id": task_id}
        new += 1
write_jsonl(cache_path, [cache[k] for k in sorted(cache)])

def qrels(include_parcial: bool) -> list[dict]:
    out = []
    for q in sorted(origin):
        rel = set(origin[q])
        rel |= {c for (qq, c), r in cache.items() if qq == q and (r["relevance"] == "si" or (include_parcial and r["relevance"] == "parcial"))}
        out += [{"qid": q, "docid": c, "relevance": 1} for c in sorted(rel)]
    return out

main_q, parcial_q = qrels(False), qrels(True)
write_jsonl(out_dir / f"eval_{split}_qrels_pooled.jsonl", main_q)
write_jsonl(out_dir / f"eval_{split}_qrels_pooled_parcial.jsonl", parcial_q)

rng = random.Random(config.SEED)
by_v: dict[str, list] = {}
for r in sorted(cache.values(), key=lambda r: (r["qid"], r["chunk_id"])):
    by_v.setdefault(r["relevance"], []).append(r)
sample = []
for v, rows in by_v.items():
    rng.shuffle(rows)
    sample += rows[: max(5, round(args.human_sample * len(rows) / max(1, len(cache))))]
rng.shuffle(sample)
with open(out_dir / f"human_review_pool_{split}.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["qid", "chunk_id", "pregunta", "titulo_chunk", "texto_chunk_(primeros_900)", "relevancia_juez", "relevancia_humano(si/parcial/no)", "notas"])
    for r in sample:
        c = corpus[r["chunk_id"]]
        w.writerow([r["qid"], r["chunk_id"], question[r["qid"]], c["title"], c["text"][:900].replace("\n", " "), r["relevance"], "", ""])

verd = Counter(r["relevance"] for r in cache.values())
nq = len(origin)
rep = {"split": split, "preguntas": nq, "pares_juzgados": len(cache), "nuevos_en_esta_corrida": new, "tareas_pendientes": pending,
       "tareas_invalidas": bad, "veredictos": dict(verd), "jueces": dict(Counter(r["judge_model"] for r in cache.values())),
       "positivos_origen": sum(len(v) for v in origin.values()), "positivos_ampliados_si": len(main_q),
       "positivos_ampliados_si_parcial": len(parcial_q),
       "positivos_extra_por_pregunta_si": round((len(main_q) - sum(len(v) for v in origin.values())) / max(1, nq), 2),
       "muestra_humana": len(sample)}
write_json(out_dir / f"pool_{split}_report.json", rep)
print(json.dumps(rep, ensure_ascii=False, indent=1))
if pending or bad:
    print(f"\nFaltan {pending} tareas por responder y {len(bad)} están mal formadas: repítelas y vuelve a ejecutar ingest.")
    sys.exit(3)
