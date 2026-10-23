#!/usr/bin/env python
"""Paso 4: hard negatives del MISMO tipo de fuente, elegidos de forma determinista (sin LLM), solo de chunks de train.

Problema del pipeline v1: el pool de negativos excluía toda la norma de los positivos (p. ej. toda la Ley 30364),
así que 0 % de los negativos eran de la Ley 30364 mientras ~45 % de los positivos lo eran: el tipo de fuente
delataba la etiqueta y el embedding aprendió un atajo. Aquí:

  * La distribución por tipo de los negativos replica la de los positivos (se mide en el paso 6 con un AUC).
  * Los negativos salen de un BM25 sobre (pregunta + foco de la respuesta + títulos de los positivos), para que
    sean cercanos al tema; nunca de dev/test ni de chunks excluidos.
  * Se excluyen: los positivos, sus duplicados, los artículos hermanos (22-A / 22-B cuando el positivo es el 22) y
    los casi idénticos (Jaccard >= 0.8). Un mismo chunk no es negativo de más de MAX_NEG_USES preguntas.
  * Para preguntas de casos, hasta CASE_CANDIDATE_NEGS candidatos del caso no elegidos como positivos se usan como
    negativos "difíciles"; marcados para juzgarse siempre (son los más propensos a ser falsos negativos).

Uso: python 04_select_negatives.py [--out-dir DIR]
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import config
from common import (check_freeze, BM25, article_base, jaccard, load_corpus, read_json, read_jsonl, source_code, stable_unit,
                    write_json, write_jsonl)

ap = argparse.ArgumentParser()
ap.add_argument("--chunks", default=str(config.CHUNKS_PATH))
ap.add_argument("--out-dir", default=str(config.OUT_DIR))
ap.add_argument("--n", type=int, default=config.N_NEG_SELECT)
args = ap.parse_args()
out_dir = Path(args.out_dir)
check_freeze(out_dir, Path(args.chunks))

corpus = load_corpus(Path(args.chunks))
sp = read_json(out_dir / "chunk_split.json")
assign = sp["assignments"]
group_of = {cid: g for g in sp.get("duplicate_groups", []) for cid in g}
train_ids = sorted(c for c, s in assign.items() if s == "train")

questions = []
for name in ("case_questions.jsonl", "chunk_questions_train.jsonl"):
    path = out_dir / name
    if path.exists():
        questions += read_jsonl(path)
questions = sorted((q for q in questions if q["split"] == "train"), key=lambda q: q["dataset_id"])
if not questions:
    raise SystemExit("No hay preguntas de train: ejecuta antes los pasos 02 y 03.")

# distribución por tipo de los positivos (objetivo para los negativos)
pos_type = Counter(source_code(corpus[p]) for q in questions for p in q["positive_chunk_ids"])
tot = sum(pos_type.values())
pi = {t: n / tot for t, n in pos_type.items()}

bm25 = BM25(train_ids, [(corpus[c].get("title") or "") + " " + corpus[c]["text"] for c in train_ids])
by_base = defaultdict(list)
for c in train_ids:
    b = article_base(corpus[c])
    if b:
        by_base[b].append(c)


def allocate(n: int, key: str) -> dict[str, int]:
    types = sorted(pi)
    raw = {t: n * pi[t] for t in types}
    base = {t: int(raw[t]) for t in types}
    order = sorted(types, key=lambda t: -(raw[t] - base[t] + 0.2 * stable_unit(key, t)))
    for t in order[: n - sum(base.values())]:
        base[t] += 1
    return base


uses: Counter = Counter()
rows, stats = [], Counter()
for q in questions:
    pos = q["positive_chunk_ids"]
    excluded = set(pos)
    for p in pos:
        excluded.update(group_of.get(p, []))
        b = article_base(corpus[p])
        if b and config.SIBLING_NEG_EXCLUSION:
            excluded.update(by_base.get(b, []))
    pos_texts = [corpus[p]["text"] for p in pos]
    qtext = " ".join([q["query"], q.get("expected_answer_focus") or ""] + [corpus[p].get("title") or "" for p in pos])
    ranked = bm25.rank(qtext, config.BM25_DEPTH)
    score_of = dict(bm25.rank(qtext, len(train_ids)))
    pos_score = max((score_of.get(p, 0.0) for p in pos), default=0.0)
    case_cands = set(q.get("candidate_chunk_ids") or []) - excluded

    def usable(cid: str) -> bool:
        if cid in excluded or uses[cid] >= config.MAX_NEG_USES or cid not in assign or assign[cid] != "train":
            return False
        if pos_score > 0 and score_of.get(cid, 0.0) >= config.NEG_MAX_SCORE_RATIO * pos_score:
            return False
        return all(jaccard(corpus[cid]["text"], t) < config.NEAR_DUP_JACCARD for t in pos_texts)

    chosen: list[dict] = []
    taken: set[str] = set()

    def take(cid: str, rank: int, from_case: bool) -> None:
        taken.add(cid)
        uses[cid] += 1
        chosen.append({"chunk_id": cid, "type": source_code(corpus[cid]), "rank": rank, "from_case_candidates": from_case})

    if q["source"] == "case" and config.CASE_CANDIDATE_NEGS > 0:   # candidatos del caso no elegidos
        for rank, (cid, _) in enumerate(ranked):
            if len([c for c in chosen if c["from_case_candidates"]]) >= config.CASE_CANDIDATE_NEGS:
                break
            if cid in case_cands and cid not in taken and usable(cid):
                take(cid, rank, True)

    by_type = defaultdict(list)
    for rank, (cid, _) in enumerate(ranked):
        if rank >= config.NEG_MIN_RANK:
            by_type[source_code(corpus[cid])].append((rank, cid))
    for t, k in allocate(args.n, q["dataset_id"]).items():
        got = len([c for c in chosen if c["type"] == t])
        for rank, cid in by_type.get(t, []):
            if len(chosen) >= args.n or got >= k:
                break
            if cid not in taken and usable(cid):
                take(cid, rank, False)
                got += 1
    for rank, (cid, _) in enumerate(ranked):             # completar con lo mejor disponible de cualquier tipo
        if len(chosen) >= args.n:
            break
        if rank < config.NEG_MIN_RANK:
            continue
        if cid not in taken and usable(cid):
            take(cid, rank, False)
    if len(chosen) < args.n:
        stats["preguntas_con_menos_negativos"] += 1
    rows.append({"dataset_id": q["dataset_id"], "negatives": chosen,
                 "must_judge": [c["chunk_id"] for c in chosen if c["from_case_candidates"]]})

write_jsonl(out_dir / "negatives.jsonl", rows)
neg_type = Counter(c["type"] for r in rows for c in r["negatives"])
nt = sum(neg_type.values())
stats.update({"preguntas": len(rows), "negativos": nt, "chunks_distintos_como_negativo": len(uses),
              "uso_maximo_de_un_chunk": max(uses.values(), default=0)})
print("tipo   % positivos   % negativos")
for t in sorted(set(pi) | set(neg_type)):
    print(f"{t:5}  {pi.get(t, 0):10.1%}  {neg_type.get(t, 0) / nt:10.1%}")
write_json(out_dir / "negatives_report.json", {**stats, "pos_type_share": pi,
                                               "neg_type_share": {t: n / nt for t, n in neg_type.items()}})
print(dict(stats))
