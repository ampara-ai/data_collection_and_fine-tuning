#!/usr/bin/env python
"""Paso 6: arma el dataset final y ejecuta las auditorías.

Entrenamiento (training.json, JSONL compatible con FlagEmbedding / el notebook actual):
  * un registro por (pregunta, positivo): query, pos[1 texto], neg[N textos]; los negativos nunca incluyen un
    positivo de la misma pregunta (ni su duplicado) para no crear falsos negativos con InfoNCE;
  * positivos = solo los que el juez marcó "si"; negativos "si" del juez se PROMUEVEN a positivos, los "parcial"
    se descartan; tope de MAX_ROWS_PER_POSITIVE filas por chunk positivo;
  * cada texto es exactamente el texto del chunk del corpus y se guarda también su chunk_id.
Evaluación (dev y test, formato del set unseen): preguntas sobre chunks que el entrenamiento nunca vio (ni como
positivo ni como negativo); solo preguntas cuyo chunk de origen el juez confirmó.

Auditorías (el paso falla si alguna se rompe): ningún chunk dev/test en train, cero preguntas duplicadas, texto de cada
positivo/negativo idéntico al corpus, AUC del tipo de fuente <= MAX_TYPE_AUC, tasa estimada de falsos negativos.

Uso: python 06_build_dataset.py [--allow-unjudged]   (esto último solo para pruebas con backend mock)
"""
import argparse
import datetime
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import config
from common import (check_freeze, load_corpus, public_chunk, read_json, read_jsonl, sha256_file, source_code, stable_unit,
                    write_json, write_jsonl)

ap = argparse.ArgumentParser()
ap.add_argument("--chunks", default=str(config.CHUNKS_PATH))
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
ap.add_argument("--allow-unjudged", action="store_true", help="acepta pares sin juicio (solo pruebas)")
ap.add_argument("--no-fail", action="store_true", help="no abortar por las auditorías (solo diagnóstico)")
ap.add_argument("--max-rows-per-positive", type=int, default=config.MAX_ROWS_PER_POSITIVE)
ap.add_argument("--n-neg", type=int, default=config.N_NEG_FINAL)
ap.add_argument("--snapshot", default=None, help="copia las salidas a <out-dir>/snapshots/<nombre> (p. ej. ola_20)")
args = ap.parse_args()
out_dir = Path(args.out_dir)
check_freeze(out_dir, Path(args.chunks))

corpus = load_corpus(Path(args.chunks))
split_doc = read_json(out_dir / "chunk_split.json")
assign = split_doc["assignments"]
group_of = {cid: g for g in split_doc.get("duplicate_groups", []) for cid in g}


def load(*names):
    rows = []
    for n in names:
        if (out_dir / n).exists():
            rows += read_jsonl(out_dir / n)
    return rows


train_q = load("case_questions.jsonl", "chunk_questions_train.jsonl")
eval_q = {"dev": load("chunk_questions_dev.jsonl"), "test": load("chunk_questions_test.jsonl")}
negs = {r["dataset_id"]: r for r in load("negatives.jsonl")}
J = {(r["dataset_id"], r["chunk_id"]): r["relevance"] for r in load("judgments.jsonl")}
problems, report = [], Counter()

# ----------------------------------------------------------------- entrenamiento
final_q, rows = [], []
for q in sorted(train_q, key=lambda q: q["dataset_id"]):
    did = q["dataset_id"]
    missing = [p for p in q["positive_chunk_ids"] if (did, p) not in J]
    if missing and not args.allow_unjudged:
        report["pregunta_sin_juicio_de_positivo"] += 1
        continue
    pos = [p for p in q["positive_chunk_ids"] if J.get((did, p), "si") == "si"]
    kept_neg = []
    for c in (negs.get(did) or {}).get("negatives", []):
        rel = J.get((did, c["chunk_id"]))
        if rel == "si":
            if c["chunk_id"] not in pos:
                pos.append(c["chunk_id"])
                report["negativo_promovido_a_positivo"] += 1
        elif rel == "parcial":
            report["negativo_descartado_parcial"] += 1
        else:
            kept_neg.append(c["chunk_id"])
    if not pos:
        report["pregunta_sin_positivo_verificado"] += 1
        continue
    blocked = set(pos)
    for p in pos:
        blocked.update(group_of.get(p, []))
    kept_neg = [c for c in kept_neg if c not in blocked]
    # recorte determinista y MEZCLADO (si se recortara por orden se perdería el reparto por tipo de la selección)
    kept_neg = sorted(kept_neg, key=lambda c: stable_unit(config.SEED, 'neg_cut', did, c))[: args.n_neg]
    if len(kept_neg) < 3:
        report["pregunta_con_pocos_negativos"] += 1
        continue
    final_q.append({**q, "positive_chunk_ids_final": pos, "negative_chunk_ids_final": kept_neg})
    for p in pos:
        rows.append({"id": f"{did}::{p}", "dataset_id": did, "query": q["query"], "pos": [corpus[p]["text"]],
                     "neg": [corpus[n]["text"] for n in kept_neg], "pos_chunk_ids": [p], "neg_chunk_ids": kept_neg,
                     "source": q["source"], "case_id": q.get("case_id") or f"chunk:{q.get('origin_chunk_id')}",
                     "topic": q["topic"], "barrier": q["barrier"], "prompt": config.FINETUNING_PROMPT})

# tope de filas por chunk positivo (selección determinista)
by_pos = defaultdict(list)
for r in rows:
    by_pos[r["pos_chunk_ids"][0]].append(r)
capped = []
for p, lst in sorted(by_pos.items()):
    lst.sort(key=lambda r: stable_unit(config.SEED, "cap", r["id"]))
    capped += lst[: args.max_rows_per_positive]
    report["filas_recortadas_por_tope"] += max(0, len(lst) - args.max_rows_per_positive)
rows = sorted(capped, key=lambda r: r["id"])

# ----------------------------------------------------------------- evaluación
from common import content_tokens, jaccard  # noqa: E402
train_sets = [frozenset(content_tokens(q)) for q in {r["query"] for r in rows}]
eval_out = {}
for s, qs in eval_q.items():
    kept = []
    for q in sorted(qs, key=lambda q: q["dataset_id"]):
        origin = q["positive_chunk_ids"][0]
        if J.get((q["dataset_id"], origin)) != "si" and not args.allow_unjudged:
            report[f"eval_{s}_descartada_origen_no_confirmado"] += 1
            continue
        qt = frozenset(content_tokens(q["query"]))
        if any(len(qt & t) / max(1, len(qt | t)) >= config.NEAR_DUP_JACCARD for t in train_sets):
            report[f"eval_{s}_descartada_casi_igual_a_una_de_train"] += 1
            continue
        pcs = [public_chunk(corpus[c]) for c in q["positive_chunk_ids"]]
        kept.append({"dataset_id": q["dataset_id"], "case_id": f"heldout_{q['origin_chunk_id']}", "query": q["query"],
                     "topic": q["topic"], "barrier": q["barrier"], "expected_answer_focus": q["expected_answer_focus"],
                     "positive_chunk_ids": q["positive_chunk_ids"],
                     "positive_source_types": sorted({p["source_type"] for p in pcs}), "positive_chunks": pcs,
                     "generation": {"method": "llm_synthetic_from_chunk", "generator": q["generator_model"],
                                    "judge": config.JUDGE_MODEL, "split": s, "seen_in_training": False,
                                    "qrels_complete": False, "lexical_overlap": q["lexical_overlap"],
                                    "prompt_version": q["prompt_version"]}})
    eval_out[s] = kept
    write_jsonl(out_dir / f"eval_{s}_dataset.jsonl", kept)
    write_jsonl(out_dir / f"eval_{s}_qrels.jsonl",
                [{"qid": r["dataset_id"], "docid": c, "relevance": 1} for r in kept for c in r["positive_chunk_ids"]])
    write_jsonl(out_dir / f"eval_{s}_queries.jsonl",
                [{"id": r["dataset_id"], "text": r["query"], "topic": r["topic"], "barrier": r["barrier"]} for r in kept])

write_jsonl(out_dir / "training.json", rows)
write_jsonl(out_dir / "train_questions_final.jsonl", final_q)

# ----------------------------------------------------------------- auditorías
train_chunk_ids = {c for r in rows for c in r["pos_chunk_ids"] + r["neg_chunk_ids"]}
leak = sorted(c for c in train_chunk_ids if assign.get(c) != "train")
if leak:
    problems.append(f"{len(leak)} chunks no-train aparecen en el entrenamiento (p. ej. {leak[:3]})")
eval_chunk_ids = {c for rs in eval_out.values() for r in rs for c in r["positive_chunk_ids"]}
if train_chunk_ids & eval_chunk_ids:
    problems.append("hay chunks de evaluación en el entrenamiento")
# varias filas de entrenamiento comparten la misma pregunta (una por positivo): se comparan preguntas únicas
uq = Counter(q.strip().lower() for q in {r["query"] for r in rows}) + Counter(q.strip().lower() for rs in eval_out.values() for r in rs for q in [r["query"]])
dup_q = [q for q, n in uq.items() if n > 1]
if dup_q:
    problems.append(f"{len(dup_q)} preguntas duplicadas entre conjuntos (p. ej. {dup_q[:2]})")
for r in rows:
    for cid, txt in zip(r["pos_chunk_ids"] + r["neg_chunk_ids"], r["pos"] + r["neg"]):
        if corpus[cid]["text"] != txt:
            problems.append(f"texto distinto al corpus en {r['id']} / {cid}")
            break

# AUC del tipo de fuente como predictor de la etiqueta (positivo vs negativo)
P, N = Counter(), Counter()
for r in rows:
    for c in r["pos_chunk_ids"]:
        P[source_code(corpus[c])] += 1
    for c in r["neg_chunk_ids"]:
        N[source_code(corpus[c])] += 1
score = {t: P[t] / (P[t] + N[t]) for t in set(P) | set(N)}
wins = sum(P[a] * N[b] * (1.0 if score[a] > score[b] else 0.5 if score[a] == score[b] else 0.0) for a in P for b in N)
auc = wins / max(1, sum(P.values()) * sum(N.values()))
if auc > config.MAX_TYPE_AUC:
    msg = f"el tipo de fuente predice la etiqueta: AUC={auc:.3f} > {config.MAX_TYPE_AUC}"
    if len(rows) >= config.MIN_ROWS_FOR_AUC_CHECK:
        problems.append(msg)
    else:
        report["aviso_auc_con_pocas_filas"] = msg + f" (solo {len(rows)} filas: no concluyente)"

# tasa de falsos negativos entre los negativos juzgados
neg_j = [r for r in load("judgments.jsonl") if r["role"] == "negative"]
fn = sum(r["relevance"] == "si" for r in neg_j)
fn_rate = fn / len(neg_j) if neg_j else None
if neg_j:
    report["negativos_parcial_pct"] = round(100 * sum(r["relevance"] == "parcial" for r in neg_j) / len(neg_j), 1)
if fn_rate is not None and neg_j:
    half = 1.96 * math.sqrt(fn_rate * (1 - fn_rate) / len(neg_j))
    report["negativos_juzgados"] = len(neg_j)
    report["negativos_si_estimados_pct"] = round(100 * fn_rate, 1)
    report["negativos_si_ic95_pct"] = [round(100 * max(0, fn_rate - half), 1), round(100 * min(1, fn_rate + half), 1)]
    if fn_rate > config.MAX_FALSE_NEGATIVE_SI_RATE:
        problems.append(f"{fn_rate:.1%} de los negativos juzgados son 'si' (> {config.MAX_FALSE_NEGATIVE_SI_RATE:.0%}): "
                        f"sube NEG_MIN_RANK o juzga todos los negativos (--neg-fraction 1.0)")

train_pool = [c for c, s in assign.items() if s == "train"]
rows_per_chunk = Counter(r["pos_chunk_ids"][0] for r in rows)
cov = {
    "filas": len(rows), "preguntas": len(final_q), "positivos_distintos": len(rows_per_chunk),
    "chunks_train": len(train_pool), "chunks_train_con_>=1_fila": sum(c in rows_per_chunk for c in train_pool),
    "chunks_train_con_>=3_filas": sum(rows_per_chunk[c] >= 3 for c in train_pool),
    "max_filas_en_un_positivo": max(rows_per_chunk.values(), default=0),
    "pct_positivos_por_tipo": {t: round(n / sum(P.values()), 3) for t, n in sorted(P.items())},
    "pct_negativos_por_tipo": {t: round(n / sum(N.values()), 3) for t, n in sorted(N.items())},
    "auc_tipo_de_fuente": round(auc, 3),
    "filas_por_origen": dict(Counter(r["source"] for r in rows)),
    "eval": {s: len(rs) for s, rs in eval_out.items()},
}
write_json(out_dir / "build_report.json", {"cobertura": cov, "contadores": dict(report), "problemas": problems})
write_json(out_dir / "manifest.json", {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "prompt_version": config.PROMPT_VERSION,
    "seed": config.SEED, "generator_model": config.GENERATOR_MODEL, "judge_model": config.JUDGE_MODEL,
    "inputs_sha256": {"document_chunks_all": sha256_file(Path(args.chunks)), "chunk_split": sha256_file(out_dir / "chunk_split.json")},
    "outputs_sha256": {n: sha256_file(out_dir / n) for n in ["training.json", "eval_dev_dataset.jsonl", "eval_test_dataset.jsonl"]},
    "params": {k: getattr(config, k) for k in ["TEST_FRAC", "DEV_FRAC", "CHUNK_QUESTIONS", "MAX_LEXICAL_OVERLAP", "N_NEG_SELECT",
                                              "N_NEG_FINAL", "MAX_NEG_USES", "MAX_ROWS_PER_POSITIVE", "NEG_JUDGE_FRACTION"]},
    "provenance": {"generator_models": dict(Counter(q["generator_model"] for q in final_q)),
                   "judge_models": dict(Counter(r["judge_model"] for r in load("judgments.jsonl")))},
    "counts": cov, "audit_problems": problems})
import json
if args.snapshot:
    import shutil
    snap = out_dir / "snapshots" / args.snapshot
    snap.mkdir(parents=True, exist_ok=True)
    for n in ["training.json", "train_questions_final.jsonl", "eval_dev_dataset.jsonl", "eval_test_dataset.jsonl", "eval_dev_qrels.jsonl",
              "eval_test_qrels.jsonl", "eval_dev_queries.jsonl", "eval_test_queries.jsonl", "build_report.json", "manifest.json",
              "judgments.jsonl", "negatives.jsonl", "case_questions.jsonl", "chunk_questions_train.jsonl", "chunk_questions_dev.jsonl",
              "chunk_questions_test.jsonl", "chunk_questions_skipped.jsonl"]:
        if (out_dir / n).exists():
            shutil.copy(out_dir / n, snap / n)
    print(f"[snapshot] copiado a {snap}")
print(json.dumps({"cobertura": cov, "contadores": dict(report)}, ensure_ascii=False, indent=1))
if problems:
    print("\nAUDITORÍA: PROBLEMAS")
    for p in problems:
        print("  -", p)
    if not args.no_fail:
        sys.exit(2)
else:
    print("\nAUDITORÍA: OK")
